import sys
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import os
import re
from typing import Optional

# {ip: {date: count}} — used for anonymous users only
_rate_counts: dict = defaultdict(lambda: defaultdict(int))
ANON_DAILY_LIMIT = 3

# Configurable generation limits (env-overridable)
FREE_LIFETIME_LIMIT = int(os.environ.get("FREE_LIFETIME_LIMIT", "10"))
CREATOR_MONTHLY_LIMIT = int(os.environ.get("CREATOR_MONTHLY_LIMIT", "300"))
PRO_MONTHLY_LIMIT = int(os.environ.get("PRO_MONTHLY_LIMIT", "1000"))

APP_URL = os.environ.get("APP_URL", "http://localhost:8000")

sys.path.insert(0, str(Path(__file__).parent))

from core.claude_client import stream_variations
from core.midi_writer import write_midi
from core.audio_renderer import render_midi_to_wav
from core.drum_synth import render_drum_pattern
from core.variations import extract_variation_info, validate_variation, sanitize_variation
from core.auth import create_jwt, get_current_user, google_auth_url, exchange_google_code
from core.storage import upload_to_r2, r2_enabled

app = FastAPI()

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

WEB_DIR = Path(__file__).parent / "web"

# ---------------------------------------------------------------------------
# DB initialisation on startup (graceful — skipped if DATABASE_URL not set)
# ---------------------------------------------------------------------------
try:
    from core.db import Base, engine, SessionLocal, get_db
    from core.models import User, Folder, SavedFile

    if engine is not None:
        Base.metadata.create_all(bind=engine)
        _db_available = True
    else:
        _db_available = False
except Exception:
    _db_available = False
    SessionLocal = None

    def get_db():  # type: ignore[misc]
        yield None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].strip("-")


def _url_to_local_path(url: str) -> Optional[Path]:
    """Convert a relative output URL like /output/slug/file.mid to an absolute Path."""
    if not url.startswith("/output/"):
        return None
    rel = url[len("/output/"):]
    return OUTPUT_DIR / rel


def _stripe_enabled() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY", ""))


def _check_and_increment_generation(user, db, ip: str) -> None:
    """Check rate/quota limits and increment the counter.

    Raises HTTPException 402 when a limit is reached.
    Raises HTTPException 429 for anonymous IP-based rate limiting.
    """
    # Anonymous path — IP-based daily limit (existing behaviour)
    if user is None or not _stripe_enabled():
        if user is None:
            today = date.today()
            admin_ips = {x.strip() for x in os.environ.get("ADMIN_IPS", "").split(",") if x.strip()}
            if ip not in admin_ips:
                if _rate_counts[ip][today] >= ANON_DAILY_LIMIT:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Limit of {ANON_DAILY_LIMIT} generations per day reached. Sign in for more!"
                    )
                _rate_counts[ip][today] += 1
        return  # logged-in but Stripe disabled — no quota enforcement

    # Reset monthly counter if the reset date has passed
    now = datetime.now(timezone.utc)
    if user.monthly_reset_date and now >= user.monthly_reset_date:
        user.monthly_generations = 0
        user.monthly_reset_date = now + timedelta(days=30)

    plan = user.subscription_plan
    status = user.subscription_status
    is_active = status == "active"

    if plan == "pro" and is_active:
        if user.monthly_generations >= PRO_MONTHLY_LIMIT:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "limit_reached",
                    "plan": "pro",
                    "limit": PRO_MONTHLY_LIMIT,
                    "upgrade_url": "/api/stripe/checkout/pro",
                }
            )
        user.monthly_generations = (user.monthly_generations or 0) + 1

    elif plan == "creator" and is_active:
        if user.monthly_generations >= CREATOR_MONTHLY_LIMIT:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "limit_reached",
                    "plan": "creator",
                    "limit": CREATOR_MONTHLY_LIMIT,
                    "upgrade_url": "/api/stripe/checkout/pro",
                }
            )
        user.monthly_generations = (user.monthly_generations or 0) + 1

    else:
        # Free tier
        if (user.lifetime_generations or 0) >= FREE_LIFETIME_LIMIT:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "limit_reached",
                    "plan": "free",
                    "limit": FREE_LIFETIME_LIMIT,
                    "upgrade_url": "/api/stripe/checkout/creator",
                }
            )
        user.lifetime_generations = (user.lifetime_generations or 0) + 1

    db.commit()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    prompt: str


class CreateFolderRequest(BaseModel):
    name: str


class SaveFileRequest(BaseModel):
    name: str
    prompt: str
    midi_url: str
    wav_url: Optional[str] = None
    folder_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Existing generation logic
# ---------------------------------------------------------------------------

def _process_variation(var: dict, gm_patch: int, slug: str, is_drums: bool = False) -> dict:
    var = sanitize_variation(var)
    validate_variation(var)
    info = extract_variation_info(var)
    idx = str(info.id).zfill(2)
    var_slug = slugify(info.name)
    out_dir = OUTPUT_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    midi_path = out_dir / f"{idx}-{var_slug}.mid"
    wav_path = out_dir / f"{idx}-{var_slug}.wav"

    channel = 9 if is_drums else 0
    write_midi(midi_path, var["notes"], info.tempo, gm_patch, channel)

    if is_drums:
        wav_ok = render_drum_pattern(var["notes"], info.tempo, wav_path)
    else:
        wav_ok = render_midi_to_wav(midi_path, wav_path)

    return {
        "id": info.id,
        "name": info.name,
        "character": info.character,
        "tempo": info.tempo,
        "note_count": info.note_count,
        "midi_url": f"/output/{slug}/{midi_path.name}",
        "wav_url": f"/output/{slug}/{wav_path.name}" if wav_ok else None,
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest, request: Request, db=Depends(get_db)):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    user = get_current_user(request, db) if db is not None else None

    # Check admin bypass only for anonymous / old path
    if user is None:
        admin_ips = {x.strip() for x in os.environ.get("ADMIN_IPS", "").split(",") if x.strip()}
        if ip in admin_ips:
            # Skip all rate limiting for admins
            pass
        else:
            _check_and_increment_generation(user, db, ip)
    else:
        _check_and_increment_generation(user, db, ip)

    slug = slugify(req.prompt)
    gm_patch = 0
    is_drums = False

    def event_stream():
        nonlocal gm_patch, is_drums
        try:
            for event in stream_variations(req.prompt):
                if event["type"] == "meta":
                    gm_patch = event["gm_patch"]
                    is_drums = event.get("is_drums", False)
                    yield f"data: {json.dumps(event)}\n\n"
                elif event["type"] == "variation":
                    try:
                        result = _process_variation(event["variation"], gm_patch, slug, is_drums)
                        yield f"data: {json.dumps({'type': 'variation', **result})}\n\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                elif event["type"] == "done":
                    yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.get("/auth/google")
async def auth_google():
    url = google_auth_url()
    return RedirectResponse(url=url)


@app.get("/auth/callback")
async def auth_callback(code: str, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    try:
        profile = await exchange_google_code(code)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OAuth exchange failed: {exc}")

    # Upsert the user
    user = db.query(User).filter(User.google_id == profile["google_id"]).first()
    if user is None:
        import uuid
        user = User(
            id=str(uuid.uuid4()),
            google_id=profile["google_id"],
            email=profile["email"],
            name=profile["name"],
            picture=profile.get("picture"),
        )
        db.add(user)
    else:
        user.email = profile["email"]
        user.name = profile["name"]
        user.picture = profile.get("picture")

    db.commit()
    db.refresh(user)

    token = create_jwt(user.id)
    response = RedirectResponse(url="/")
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
        secure=os.environ.get("APP_URL", "").startswith("https"),
    )
    return response


@app.post("/auth/logout")
async def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("token")
    return response


@app.get("/auth/me")
async def auth_me(request: Request, db=Depends(get_db)):
    user = get_current_user(request, db)
    if user is None:
        return JSONResponse({"user": None})
    return JSONResponse({
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
        }
    })


# ---------------------------------------------------------------------------
# Stripe routes
# ---------------------------------------------------------------------------

@app.post("/api/stripe/checkout/{plan}")
async def stripe_checkout(plan: str, request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    if not _stripe_enabled():
        raise HTTPException(status_code=503, detail="Stripe not configured")
    if plan not in ("creator", "pro"):
        raise HTTPException(status_code=400, detail="Invalid plan. Must be 'creator' or 'pro'.")

    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from core.stripe_client import create_checkout_session, create_customer

    # Ensure the Stripe customer record exists and is persisted
    if not user.stripe_customer_id:
        customer_id = create_customer(user)
        if customer_id:
            user.stripe_customer_id = customer_id
            db.commit()

    success_url = APP_URL.rstrip("/") + "/?subscribed=1"
    cancel_url = APP_URL.rstrip("/") + "/"

    url = create_checkout_session(user, plan, success_url, cancel_url)
    if url is None:
        raise HTTPException(status_code=500, detail="Failed to create checkout session. Check price IDs.")

    return JSONResponse({"url": url})


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request, db=Depends(get_db)):
    """Stripe webhook — must read raw body for signature verification."""
    raw_body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    stripe_mod = None
    if _stripe_enabled():
        from core.stripe_client import get_stripe_client
        stripe_mod = get_stripe_client()

    if stripe_mod is None:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    try:
        event = stripe_mod.Webhook.construct_event(raw_body, sig_header, webhook_secret)
    except stripe_mod.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Webhook error: {exc}")

    event_type = event["type"]
    data_obj = event["data"]["object"]

    creator_price_id = os.environ.get("STRIPE_CREATOR_PRICE_ID", "")
    pro_price_id = os.environ.get("STRIPE_PRO_PRICE_ID", "")

    def _get_user_by_customer(customer_id: str):
        if db is None:
            return None
        return db.query(User).filter(User.stripe_customer_id == customer_id).first()

    def _plan_from_subscription(subscription) -> Optional[str]:
        """Determine plan name from subscription's price items."""
        try:
            for item in subscription["items"]["data"]:
                pid = item["price"]["id"]
                if pid == pro_price_id:
                    return "pro"
                if pid == creator_price_id:
                    return "creator"
        except (KeyError, TypeError):
            pass
        return None

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        customer_id = data_obj.get("customer")
        user = _get_user_by_customer(customer_id)
        if user and db:
            plan = _plan_from_subscription(data_obj)
            user.stripe_subscription_id = data_obj["id"]
            user.subscription_plan = plan
            user.subscription_status = data_obj.get("status")
            db.commit()

    elif event_type == "customer.subscription.deleted":
        customer_id = data_obj.get("customer")
        user = _get_user_by_customer(customer_id)
        if user and db:
            user.subscription_plan = None
            user.subscription_status = "canceled"
            db.commit()

    elif event_type == "invoice.payment_succeeded":
        customer_id = data_obj.get("customer")
        user = _get_user_by_customer(customer_id)
        if user and db:
            now = datetime.now(timezone.utc)
            user.monthly_generations = 0
            user.monthly_reset_date = now + timedelta(days=30)
            db.commit()

    return JSONResponse({"received": True})


@app.get("/api/stripe/status")
async def stripe_status(request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    plan = user.subscription_plan
    status = user.subscription_status
    is_active = status == "active"

    if plan == "pro" and is_active:
        used = user.monthly_generations or 0
        remaining = max(0, PRO_MONTHLY_LIMIT - used)
        limit = PRO_MONTHLY_LIMIT
        period = "monthly"
    elif plan == "creator" and is_active:
        used = user.monthly_generations or 0
        remaining = max(0, CREATOR_MONTHLY_LIMIT - used)
        limit = CREATOR_MONTHLY_LIMIT
        period = "monthly"
    else:
        used = user.lifetime_generations or 0
        remaining = max(0, FREE_LIFETIME_LIMIT - used)
        limit = FREE_LIFETIME_LIMIT
        period = "lifetime"
        plan = "free"
        status = None

    return JSONResponse({
        "plan": plan,
        "status": status,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "period": period,
        "stripe_enabled": _stripe_enabled(),
    })


@app.post("/api/stripe/cancel")
async def stripe_cancel(request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    if not _stripe_enabled():
        raise HTTPException(status_code=503, detail="Stripe not configured")

    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription to cancel")

    from core.stripe_client import cancel_subscription
    ok = cancel_subscription(user.stripe_subscription_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")

    user.subscription_status = "canceled"
    db.commit()
    return JSONResponse({"ok": True, "message": "Subscription will cancel at period end."})


# ---------------------------------------------------------------------------
# Folder routes
# ---------------------------------------------------------------------------

@app.get("/api/folders")
async def list_folders(request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    folders = db.query(Folder).filter(Folder.user_id == user.id).order_by(Folder.created_at).all()
    result = []
    for folder in folders:
        file_count = db.query(SavedFile).filter(SavedFile.folder_id == folder.id).count()
        result.append({
            "id": folder.id,
            "name": folder.name,
            "created_at": folder.created_at.isoformat(),
            "file_count": file_count,
        })
    return JSONResponse(result)


@app.post("/api/folders")
async def create_folder(body: CreateFolderRequest, request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Folder name is required")

    import uuid
    folder = Folder(id=str(uuid.uuid4()), user_id=user.id, name=body.name.strip())
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return JSONResponse({
        "id": folder.id,
        "name": folder.name,
        "created_at": folder.created_at.isoformat(),
        "file_count": 0,
    })


@app.delete("/api/folders/{folder_id}")
async def delete_folder(folder_id: str, request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    folder = db.query(Folder).filter(Folder.id == folder_id, Folder.user_id == user.id).first()
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")

    db.delete(folder)
    db.commit()
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Save / library routes
# ---------------------------------------------------------------------------

@app.post("/api/save")
async def save_file(body: SaveFileRequest, request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Validate folder ownership if provided
    if body.folder_id:
        folder = db.query(Folder).filter(
            Folder.id == body.folder_id, Folder.user_id == user.id
        ).first()
        if folder is None:
            raise HTTPException(status_code=404, detail="Folder not found")

    midi_url = body.midi_url
    wav_url = body.wav_url

    # Optionally upload to R2
    if r2_enabled():
        midi_local = _url_to_local_path(body.midi_url)
        if midi_local and midi_local.exists():
            key = f"saved/{user.id}/{midi_local.name}"
            r2_midi = upload_to_r2(midi_local, key)
            if r2_midi:
                midi_url = r2_midi

        if body.wav_url:
            wav_local = _url_to_local_path(body.wav_url)
            if wav_local and wav_local.exists():
                key = f"saved/{user.id}/{wav_local.name}"
                r2_wav = upload_to_r2(wav_local, key)
                if r2_wav:
                    wav_url = r2_wav

    import uuid
    saved = SavedFile(
        id=str(uuid.uuid4()),
        user_id=user.id,
        folder_id=body.folder_id or None,
        name=body.name,
        prompt=body.prompt,
        midi_url=midi_url,
        wav_url=wav_url,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)

    return JSONResponse({
        "id": saved.id,
        "name": saved.name,
        "prompt": saved.prompt,
        "midi_url": saved.midi_url,
        "wav_url": saved.wav_url,
        "folder_id": saved.folder_id,
        "created_at": saved.created_at.isoformat(),
    })


@app.get("/api/saved")
async def list_saved(request: Request, folder_id: Optional[str] = None, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    query = db.query(SavedFile).filter(SavedFile.user_id == user.id)
    if folder_id is not None:
        query = query.filter(SavedFile.folder_id == folder_id)
    files = query.order_by(SavedFile.created_at.desc()).all()

    result = [
        {
            "id": f.id,
            "name": f.name,
            "prompt": f.prompt,
            "midi_url": f.midi_url,
            "wav_url": f.wav_url,
            "folder_id": f.folder_id,
            "created_at": f.created_at.isoformat(),
        }
        for f in files
    ]
    return JSONResponse(result)


@app.delete("/api/saved/{file_id}")
async def delete_saved(file_id: str, request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    saved = db.query(SavedFile).filter(SavedFile.id == file_id, SavedFile.user_id == user.id).first()
    if saved is None:
        raise HTTPException(status_code=404, detail="File not found")

    db.delete(saved)
    db.commit()
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Static file mounts (must come last)
# ---------------------------------------------------------------------------

app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
