import sys
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import os
import re
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text

_wav_executor = ThreadPoolExecutor(max_workers=4)

# Configurable generation limits (env-overridable)
ANON_LIFETIME_LIMIT = int(os.environ.get("ANON_LIFETIME_LIMIT", "5"))
FREE_LIFETIME_LIMIT = int(os.environ.get("FREE_LIFETIME_LIMIT", "15"))
CREATOR_MONTHLY_LIMIT = int(os.environ.get("CREATOR_MONTHLY_LIMIT", "300"))
PRO_MONTHLY_LIMIT = int(os.environ.get("PRO_MONTHLY_LIMIT", "1000"))

APP_URL = os.environ.get("APP_URL", "http://localhost:8000")

sys.path.insert(0, str(Path(__file__).parent))

from core.claude_client import stream_variations, stream_thinking
from core.midi_writer import write_midi
from core.audio_renderer import render_midi_to_wav
from core.expression import apply_expression
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
    from core.models import User, Folder, SavedFile, Project

    if engine is not None:
        Base.metadata.create_all(bind=engine)
        try:
            with engine.connect() as _conn:
                _conn.execute(text(
                    "ALTER TABLE saved_files ADD COLUMN IF NOT EXISTS project_id VARCHAR "
                    "REFERENCES projects(id) ON DELETE SET NULL"
                ))
                _conn.commit()
        except Exception:
            pass
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
    # Admin emails get unlimited generations
    if user is not None:
        admin_emails = {x.strip().lower() for x in os.environ.get("ADMIN_EMAILS", "").split(",") if x.strip()}
        if user.email.lower() in admin_emails:
            return

    # Anonymous path — handled in the generate endpoint (needs request/response for cookie)
    if user is None or not _stripe_enabled():
        return  # logged-in but Stripe disabled — no quota enforcement

    # Reset monthly counter if the reset date has passed
    now = datetime.utcnow()
    reset_date = user.monthly_reset_date
    if reset_date and reset_date.tzinfo is not None:
        reset_date = reset_date.replace(tzinfo=None)
    if reset_date and now >= reset_date:
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
    history: list = []


class SaveProjectFileRequest(BaseModel):
    name: str
    prompt: str
    midi_url: str
    wav_url: Optional[str] = None

class SaveProjectRequest(BaseModel):
    name: str
    files: list[SaveProjectFileRequest] = []


# ---------------------------------------------------------------------------
# Existing generation logic
# ---------------------------------------------------------------------------

def _render_wav(notes, tempo, is_drums, drum_kit, midi_path, wav_path, gm_patch=None):
    """Runs in background thread — renders WAV after MIDI is written."""
    try:
        if is_drums:
            ok = render_drum_pattern(notes, tempo, wav_path, kit_name=drum_kit)
            if not ok:
                render_midi_to_wav(midi_path, wav_path, gm_patch=gm_patch)
        else:
            render_midi_to_wav(midi_path, wav_path, gm_patch=gm_patch)
    except Exception as e:
        print(f"  [warn] background WAV render failed for {wav_path.name}: {e}")


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
    expression_level = var.get("expression", "subtle")

    notes = var["notes"]
    if is_drums:
        grid = 0.25
        for n in notes:
            n["time"] = round(round(float(n["time"]) / grid) * grid, 4)

    notes_with_expression = apply_expression(notes, gm_patch, expression_level, is_drums)
    write_midi(midi_path, notes_with_expression, info.tempo, gm_patch, channel)

    drum_kit = var.get("drum_kit", None) if is_drums else None

    future = _wav_executor.submit(_render_wav, list(notes), info.tempo, is_drums, drum_kit, midi_path, wav_path, gm_patch)
    future.result(timeout=30)

    return {
        "id": info.id,
        "name": info.name,
        "character": info.character,
        "tempo": info.tempo,
        "note_count": info.note_count,
        "midi_url": f"/output/{slug}/{midi_path.name}",
        "wav_url": f"/output/{slug}/{wav_path.name}" if wav_path.exists() else None,
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest, request: Request, db=Depends(get_db)):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    user = get_current_user(request, db) if db is not None else None

    # Check admin bypass only for anonymous / old path
    admin_ips = {x.strip() for x in os.environ.get("ADMIN_IPS", "").split(",") if x.strip()}
    is_admin_ip = ip in admin_ips

    # Anonymous cookie-based lifetime check
    anon_count = 0
    if user is None and not is_admin_ip:
        try:
            anon_count = int(request.cookies.get("anon_gens", "0"))
        except ValueError:
            anon_count = 0
        if anon_count >= ANON_LIFETIME_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"You've used your {ANON_LIFETIME_LIMIT} free generations. Sign in for more!"
            )

    if not is_admin_ip:
        _check_and_increment_generation(user, db, ip)

    slug = slugify(req.prompt)
    gm_patch = 0
    is_drums = False

    def event_stream():
        nonlocal gm_patch, is_drums
        try:
            for event in stream_thinking(req.prompt):
                yield f"data: {json.dumps(event)}\n\n"
            for event in stream_variations(req.prompt, req.history):
                if event["type"] == "meta":
                    gm_patch = event["gm_patch"]
                    is_drums = event.get("is_drums", False)
                    yield f"data: {json.dumps(event)}\n\n"
                elif event["type"] == "variation":
                    try:
                        result = _process_variation(event["variation"], gm_patch, slug, is_drums)
                        yield f"data: {json.dumps({'type': 'variation', **result})}\n\n"
                    except Exception as e:
                        print(f"  [warn] variation failed, skipping: {e}")
                elif event["type"] == "done":
                    yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    response = StreamingResponse(event_stream(), media_type="text/event-stream")
    if user is None and not is_admin_ip:
        response.set_cookie("anon_gens", str(anon_count + 1), max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


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

    success_url = APP_URL.rstrip("/") + f"/?subscribed={plan}"
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
            items = subscription["items"]["data"]
        except (KeyError, TypeError, AttributeError):
            try:
                items = subscription.items.data
            except Exception:
                return None
        try:
            for item in items:
                try:
                    pid = item["price"]["id"]
                except (KeyError, TypeError, AttributeError):
                    pid = item.price.id
                if pid == pro_price_id:
                    return "pro"
                if pid == creator_price_id:
                    return "creator"
        except Exception:
            pass
        return None

    def _attr(obj, key, default=None):
        """Get a field from a Stripe object whether it's dict-like or attribute-based."""
        try:
            return obj[key]
        except (KeyError, TypeError):
            pass
        try:
            return getattr(obj, key, default)
        except Exception:
            return default

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        customer_id = _attr(data_obj, "customer")
        user = _get_user_by_customer(customer_id)
        if user and db:
            plan = _plan_from_subscription(data_obj)
            user.stripe_subscription_id = _attr(data_obj, "id")
            user.subscription_plan = plan
            user.subscription_status = _attr(data_obj, "status")
            db.commit()

    elif event_type == "customer.subscription.deleted":
        customer_id = _attr(data_obj, "customer")
        user = _get_user_by_customer(customer_id)
        if user and db:
            user.subscription_plan = None
            user.subscription_status = "canceled"
            db.commit()

    elif event_type == "invoice.payment_succeeded":
        customer_id = _attr(data_obj, "customer")
        user = _get_user_by_customer(customer_id)
        if user and db:
            user.monthly_generations = 0
            user.monthly_reset_date = datetime.utcnow() + timedelta(days=30)
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



# ---------------------------------------------------------------------------
# Project routes
# ---------------------------------------------------------------------------

@app.get("/api/projects")
async def list_projects(request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    projects = db.query(Project).filter(Project.user_id == user.id).order_by(Project.created_at.desc()).all()
    result = []
    for proj in projects:
        file_count = db.query(SavedFile).filter(SavedFile.project_id == proj.id).count()
        result.append({
            "id": proj.id,
            "name": proj.name,
            "created_at": proj.created_at.isoformat(),
            "file_count": file_count,
        })
    return JSONResponse(result)


@app.post("/api/projects")
async def create_project(body: SaveProjectRequest, request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")

    import uuid as _uuid_mod
    proj = Project(id=str(_uuid_mod.uuid4()), user_id=user.id, name=body.name.strip())
    db.add(proj)
    db.flush()

    saved_ids = []
    for f in body.files:
        midi_url = f.midi_url
        wav_url = f.wav_url

        if r2_enabled():
            midi_local = _url_to_local_path(f.midi_url)
            if midi_local and midi_local.exists():
                key = f"projects/{user.id}/{proj.id}/{midi_local.name}"
                r2_midi = upload_to_r2(midi_local, key)
                if r2_midi:
                    midi_url = r2_midi

            if f.wav_url:
                wav_local = _url_to_local_path(f.wav_url)
                if wav_local and wav_local.exists():
                    key = f"projects/{user.id}/{proj.id}/{wav_local.name}"
                    r2_wav = upload_to_r2(wav_local, key)
                    if r2_wav:
                        wav_url = r2_wav

        saved = SavedFile(
            id=str(_uuid_mod.uuid4()),
            user_id=user.id,
            project_id=proj.id,
            name=f.name,
            prompt=f.prompt,
            midi_url=midi_url,
            wav_url=wav_url,
        )
        db.add(saved)
        saved_ids.append(saved.id)

    db.commit()
    db.refresh(proj)

    return JSONResponse({
        "id": proj.id,
        "name": proj.name,
        "created_at": proj.created_at.isoformat(),
        "file_count": len(body.files),
    })


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    proj = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(proj)
    db.commit()
    return JSONResponse({"ok": True})


@app.get("/api/projects/{project_id}/files")
async def list_project_files(project_id: str, request: Request, db=Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    proj = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    files = db.query(SavedFile).filter(SavedFile.project_id == project_id).order_by(SavedFile.created_at).all()
    return JSONResponse([{
        "id": f.id,
        "name": f.name,
        "prompt": f.prompt,
        "midi_url": f.midi_url,
        "wav_url": f.wav_url,
        "created_at": f.created_at.isoformat(),
    } for f in files])


# ---------------------------------------------------------------------------
# Static file mounts (must come last)
# ---------------------------------------------------------------------------

app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
