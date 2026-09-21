import sys
import json
import os
from pathlib import Path

_SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if _SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        traces_sample_rate=0.05,
        profiles_sample_rate=0.0,
        environment=os.environ.get("RAILWAY_ENVIRONMENT", "production"),
    )

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse, Response, FileResponse
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import re
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
import threading
from sqlalchemy import text

_wav_executor = ThreadPoolExecutor(max_workers=2)

# Generation concurrency: queue with bounded wait instead of a hard fail.
# 12 concurrent fits comfortably on Hobby's 8GB RAM ceiling.
MAX_CONCURRENT_GENERATIONS = int(os.environ.get("MAX_CONCURRENT_GENERATIONS", "12"))
MAX_QUEUE_LENGTH = int(os.environ.get("MAX_QUEUE_LENGTH", "30"))
QUEUE_TIMEOUT_SECONDS = int(os.environ.get("QUEUE_TIMEOUT_SECONDS", "300"))

_gen_lock = threading.Lock()
_gen_active = 0
_gen_waiting: list[str] = []


def _enqueue_generation() -> str:
    """Add caller to the queue. Returns waiter_id. Raises 503 if queue full."""
    import uuid
    waiter_id = str(uuid.uuid4())
    with _gen_lock:
        if len(_gen_waiting) >= MAX_QUEUE_LENGTH:
            raise HTTPException(
                status_code=503,
                detail="Lots of people are generating right now — try again in a minute.",
            )
        _gen_waiting.append(waiter_id)
    return waiter_id


def _try_acquire_slot(waiter_id: str) -> Optional[int]:
    """Claim a slot if available; otherwise return 1-indexed queue position."""
    global _gen_active
    with _gen_lock:
        try:
            idx = _gen_waiting.index(waiter_id)
        except ValueError:
            return None
        if idx == 0 and _gen_active < MAX_CONCURRENT_GENERATIONS:
            _gen_waiting.pop(0)
            _gen_active += 1
            return None
        return idx + 1


def _release_slot() -> None:
    global _gen_active
    with _gen_lock:
        _gen_active = max(0, _gen_active - 1)


def _abandon_queue(waiter_id: str) -> None:
    with _gen_lock:
        try:
            _gen_waiting.remove(waiter_id)
        except ValueError:
            pass

# Per-IP rate limiting (in-memory sliding window).
# Defaults: 8 generations per IP per minute, 60 per IP per hour.
# Configurable via env so we can tune without redeploying code paths.
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "8"))
RATE_LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", "60"))
_ip_hits: dict[str, list[float]] = {}
_ip_hits_lock = threading.Lock()


def _check_ip_rate_limit(ip: str) -> None:
    """Raise HTTPException 429 if this IP has exceeded the sliding-window limit."""
    import time
    now = time.time()
    minute_cutoff = now - 60
    hour_cutoff = now - 3600
    with _ip_hits_lock:
        hits = _ip_hits.get(ip, [])
        hits = [t for t in hits if t > hour_cutoff]
        minute_count = sum(1 for t in hits if t > minute_cutoff)
        if minute_count >= RATE_LIMIT_PER_MINUTE or len(hits) >= RATE_LIMIT_PER_HOUR:
            _ip_hits[ip] = hits
            raise HTTPException(
                status_code=429,
                detail="You're going a bit fast — give it a minute and try again.",
            )
        hits.append(now)
        _ip_hits[ip] = hits
        # Opportunistic cleanup to bound memory.
        if len(_ip_hits) > 10000:
            for k in list(_ip_hits.keys()):
                if not _ip_hits[k] or _ip_hits[k][-1] < hour_cutoff:
                    _ip_hits.pop(k, None)

# Configurable generation limits (env-overridable)
ANON_LIFETIME_LIMIT = int(os.environ.get("ANON_LIFETIME_LIMIT", "5"))
FREE_LIFETIME_LIMIT = int(os.environ.get("FREE_LIFETIME_LIMIT", "15"))
CREATOR_MONTHLY_LIMIT = int(os.environ.get("CREATOR_MONTHLY_LIMIT", "100"))
PRO_MONTHLY_LIMIT = int(os.environ.get("PRO_MONTHLY_LIMIT", "200"))

APP_URL = os.environ.get("APP_URL", "http://localhost:8000")

sys.path.insert(0, str(Path(__file__).parent))

from core.claude_client import stream_variations, stream_thinking, generate_variations
from core.midi_writer import write_midi, write_drum_stems
from core.audio_renderer import render_midi_to_wav
from core.expression import apply_expression
from core.drum_synth import render_drum_pattern
from core.drum_patterns import apply_skeleton
from core.guitar_synth import render_guitar_pattern
from core.variations import extract_variation_info, validate_variation, sanitize_variation
from core.auth import create_jwt, get_current_user, google_auth_url, exchange_google_code
from core.storage import upload_to_r2, copy_within_r2, r2_enabled

app = FastAPI()

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

def _cleanup_output_dir():
    """Delete output folders older than 30 minutes (files are on R2, local copies are temp)."""
    import shutil, time
    cutoff = time.time() - 30 * 60
    try:
        for folder in OUTPUT_DIR.iterdir():
            if folder.is_dir() and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
    except Exception as e:
        print(f"[cleanup] local output error: {e}")

def _cleanup_r2_generated():
    """Delete R2 files under generated/ older than 24 hours."""
    if not r2_enabled():
        return
    try:
        import boto3, time
        from botocore.config import Config
        from datetime import timezone
        account_id = os.environ["R2_ACCOUNT_ID"]
        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        bucket = os.environ["R2_BUCKET_NAME"]
        cutoff = datetime.now(timezone.utc).timestamp() - 24 * 3600
        paginator = s3.get_paginator("list_objects_v2")
        to_delete = []
        for page in paginator.paginate(Bucket=bucket, Prefix="generated/"):
            for obj in page.get("Contents", []):
                if obj["LastModified"].timestamp() < cutoff:
                    to_delete.append({"Key": obj["Key"]})
        if to_delete:
            # R2 delete_objects accepts max 1000 keys at a time
            for i in range(0, len(to_delete), 1000):
                s3.delete_objects(Bucket=bucket, Delete={"Objects": to_delete[i:i+1000]})
            print(f"[cleanup] deleted {len(to_delete)} expired R2 generated files")
    except Exception as e:
        print(f"[cleanup] R2 error: {e}")

def _start_cleanup_thread():
    import threading, time
    def loop():
        while True:
            time.sleep(600)  # every 10 minutes
            _cleanup_output_dir()
            _cleanup_r2_generated()
    t = threading.Thread(target=loop, daemon=True)
    t.start()

_cleanup_output_dir()  # clean on startup too
_start_cleanup_thread()

def _warm_drum_kit_cache():
    """Pre-download all drum kits from R2 into /tmp so the first generation is fast."""
    import threading
    def _warm():
        try:
            from core.drum_kits import get_kit_names, get_kit_dir
            names = get_kit_names()
            for name in names:
                get_kit_dir(name)
                print(f"[startup] drum kit cached: {name}")
        except Exception as e:
            print(f"[startup] drum kit pre-cache error: {e}")
    threading.Thread(target=_warm, daemon=True).start()

_warm_drum_kit_cache()

# Log audio setup at startup
try:
    import shutil
    _fs = shutil.which("fluidsynth")
    from core.audio_renderer import SOUNDFONT_PATHS
    _sf = next((p for p in SOUNDFONT_PATHS if p.exists()), None)
    print(f"[startup] fluidsynth: {_fs or 'NOT FOUND'}")
    print(f"[startup] soundfont:  {_sf or 'NOT FOUND'}")
except Exception as _e:
    print(f"[startup] audio check failed: {_e}")

WEB_DIR = Path(__file__).parent / "web"

# ---------------------------------------------------------------------------
# DB initialisation on startup (graceful — skipped if DATABASE_URL not set)
# ---------------------------------------------------------------------------
try:
    from core.db import Base, engine, SessionLocal, get_db
    from core.models import User, Folder, SavedFile, Project, WebhookEvent

    if engine is not None:
        Base.metadata.create_all(bind=engine)
        try:
            with engine.connect() as _conn:
                _conn.execute(text(
                    "ALTER TABLE saved_files ADD COLUMN IF NOT EXISTS project_id VARCHAR "
                    "REFERENCES projects(id) ON DELETE SET NULL"
                ))
                _conn.execute(text(
                    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS daw_state TEXT"
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
    seed_variation: Optional[dict] = None
    seed_variations: Optional[list] = None
    lock_key: Optional[str] = None
    lock_tempo: Optional[int] = None


class SaveProjectFileRequest(BaseModel):
    name: str
    prompt: str
    midi_url: str
    wav_url: Optional[str] = None

class PromoteFilesRequest(BaseModel):
    midi_url: str
    wav_url: Optional[str] = None

class SaveProjectRequest(BaseModel):
    name: str
    files: list[SaveProjectFileRequest] = []
    daw_state: Optional[dict] = None  # {bpm: int|None, clips: [{trackIdx, startBar, bars, variation:{wav_url,...}}]}


# ---------------------------------------------------------------------------
# Existing generation logic
# ---------------------------------------------------------------------------

def _infer_bars(notes, declared: int = None) -> int:
    """Return the loop length in bars — use Claude's declared value if valid, else infer from notes."""
    if declared in (1, 2, 4, 8, 16):
        return declared
    if not notes:
        return 4
    max_beat = max(float(n["time"]) + float(n["duration"]) for n in notes)
    if max_beat <= 4.5:
        return 1
    elif max_beat <= 8.5:
        return 2
    elif max_beat <= 16.5:
        return 4
    elif max_beat <= 32.5:
        return 8
    return 16


def _render_wav(notes, tempo, bars, is_drums, drum_kit, midi_path, wav_path, gm_patch=None):
    """Runs in background thread — renders WAV after MIDI is written."""
    from core.audio_renderer import pad_to_bar_duration
    try:
        if is_drums:
            ok = render_drum_pattern(notes, tempo, wav_path, kit_name=drum_kit)
            if not ok:
                render_midi_to_wav(midi_path, wav_path, gm_patch=gm_patch, tempo=tempo, bars=bars)
            elif wav_path.exists():
                pad_to_bar_duration(wav_path, bars * 4 * (60.0 / tempo))
        elif gm_patch is not None and 24 <= gm_patch <= 31:
            ok = render_guitar_pattern(notes, tempo, gm_patch, wav_path, bars=bars)
            if not ok:
                render_midi_to_wav(midi_path, wav_path, gm_patch=gm_patch, tempo=tempo, bars=bars)
        else:
            render_midi_to_wav(midi_path, wav_path, gm_patch=gm_patch, tempo=tempo, bars=bars)
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

    # Per-variation instrument overrides top-level fallback
    effective_patch = var.get("gm_patch", gm_patch)
    effective_drums = var.get("is_drums", is_drums)

    channel = 9 if effective_drums else 0
    expression_level = var.get("expression", "subtle")

    notes = var["notes"]
    if effective_drums:
        grid = 0.25
        for n in notes:
            n["time"] = round(round(float(n["time"]) / grid) * grid, 4)

    bars = _infer_bars(notes, declared=var.get("bars"))

    if effective_drums:
        drum_genre = var.get("drum_genre", "default")
        drum_layers = var.get("drum_layers", [])
        notes = apply_skeleton(notes, drum_genre, bars, layers=drum_layers)

    notes_with_expression = apply_expression(notes, effective_patch, expression_level, effective_drums)
    write_midi(midi_path, notes_with_expression, info.tempo, effective_patch, channel, bars=bars)

    drum_kit = var.get("drum_kit", None) if effective_drums else None

    # Write per-piece drum stem MIDIs
    drum_stem_urls = {}
    if effective_drums:
        base_name = f"{idx}-{var_slug}"
        stems = write_drum_stems(out_dir, base_name, notes_with_expression, info.tempo, bars=bars)
        drum_stem_urls = {group: f"/output/{slug}/{path.name}" for group, path in stems.items()}

    future = _wav_executor.submit(_render_wav, list(notes), info.tempo, bars, effective_drums, drum_kit, midi_path, wav_path, effective_patch)
    future.result(timeout=30)

    # Upload to R2 immediately so URLs survive container restarts
    r2_prefix = f"generated/{slug}/{idx}-{var_slug}"
    midi_url = f"/output/{slug}/{midi_path.name}"
    wav_url = f"/output/{slug}/{wav_path.name}" if wav_path.exists() else None

    if r2_enabled():
        r2_midi = upload_to_r2(midi_path, f"{r2_prefix}.mid")
        if r2_midi:
            midi_url = r2_midi
        else:
            print(f"[warn] R2 MIDI upload failed, using local fallback: {midi_path.name}")
        if wav_path.exists():
            r2_wav = upload_to_r2(wav_path, f"{r2_prefix}.wav")
            if r2_wav:
                wav_url = r2_wav
            else:
                print(f"[warn] R2 WAV upload failed, using local fallback: {wav_path.name}")
        if drum_stem_urls:
            r2_stems = {}
            for group, local_url in drum_stem_urls.items():
                stem_path = out_dir / Path(local_url).name
                r2_stem = upload_to_r2(stem_path, f"{r2_prefix}_{group}.mid")
                r2_stems[group] = r2_stem if r2_stem else local_url
            drum_stem_urls = r2_stems
    else:
        print(f"[warn] R2 not configured — files are local only (will break on container restart)")

    return {
        "id": info.id,
        "name": info.name,
        "character": info.character,
        "instrument": var.get("instrument"),
        "tempo": info.tempo,
        "key": var.get("key"),
        "bars": bars,
        "note_count": info.note_count,
        "notes": notes,
        "gm_patch": effective_patch,
        "is_drums": effective_drums,
        "midi_url": midi_url,
        "wav_url": wav_url,
        "drum_stems": drum_stem_urls if drum_stem_urls else None,
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

    if not is_admin_ip:
        _check_ip_rate_limit(ip)

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

    # Reserve a queue spot before starting the SSE stream so a full queue
    # returns a clean 503 instead of a half-opened stream.
    waiter_id = _enqueue_generation()

    slug = slugify(req.prompt)
    gm_patch = 0
    is_drums = False

    def event_stream():
        nonlocal gm_patch, is_drums
        import time as _time
        acquired = False
        try:
            start = _time.time()
            last_position = None
            last_yield = start
            while True:
                pos = _try_acquire_slot(waiter_id)
                if pos is None:
                    acquired = True
                    break
                now = _time.time()
                if now - start > QUEUE_TIMEOUT_SECONDS:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Took too long to find a slot — please try again.'})}\n\n"
                    return
                if pos != last_position:
                    yield f"data: {json.dumps({'type': 'queued', 'position': pos})}\n\n"
                    last_position = pos
                    last_yield = now
                elif now - last_yield > 15:
                    yield ": keepalive\n\n"
                    last_yield = now
                _time.sleep(0.5)

            for event in stream_thinking(req.prompt):
                yield f"data: {json.dumps(event)}\n\n"
            for event in stream_variations(req.prompt, seed_variation=req.seed_variation, lock_key=req.lock_key, lock_tempo=req.lock_tempo, seed_variations=req.seed_variations):
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
            import traceback
            print(f"[generate error] {e}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if acquired:
                _release_slot()
            else:
                _abandon_queue(waiter_id)

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

    event_id = event.get("id")
    event_type = event["type"]
    data_obj = event["data"]["object"]

    # Idempotency: skip if we've already processed this event.
    if db is not None and event_id:
        try:
            existing = db.query(WebhookEvent).filter(WebhookEvent.stripe_event_id == event_id).first()
            if existing:
                return JSONResponse({"received": True, "duplicate": True})
            db.add(WebhookEvent(stripe_event_id=event_id, event_type=event_type))
            db.commit()
        except Exception as exc:
            db.rollback()
            print(f"[stripe webhook] idempotency check failed for {event_id}: {exc}")

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

    admin_emails = {x.strip().lower() for x in os.environ.get("ADMIN_EMAILS", "").split(",") if x.strip()}
    if user.email.lower() in admin_emails:
        return JSONResponse({
            "plan": "admin",
            "status": "active",
            "used": user.lifetime_generations or 0,
            "limit": None,
            "remaining": None,
            "period": "unlimited",
            "stripe_enabled": _stripe_enabled(),
        })

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
        daw_state = None
        if proj.daw_state:
            try:
                daw_state = json.loads(proj.daw_state)
            except Exception:
                daw_state = None
        result.append({
            "id": proj.id,
            "name": proj.name,
            "created_at": proj.created_at.isoformat(),
            "file_count": file_count,
            "daw_state": daw_state,
        })
    return JSONResponse(result)


@app.post("/api/promote-files")
async def promote_files(body: PromoteFilesRequest):
    """Upload a hearted variation's files to R2 so URLs survive server restarts."""
    import uuid as _uuid_mod
    result = {"midi_url": body.midi_url, "wav_url": body.wav_url}
    if not r2_enabled():
        return result
    uid = str(_uuid_mod.uuid4())[:8]
    midi_local = _url_to_local_path(body.midi_url)
    if midi_local and midi_local.exists():
        r2_url = upload_to_r2(midi_local, f"hearted/{uid}/{midi_local.name}")
        if r2_url:
            result["midi_url"] = r2_url
    if body.wav_url:
        wav_local = _url_to_local_path(body.wav_url)
        if wav_local and wav_local.exists():
            r2_url = upload_to_r2(wav_local, f"hearted/{uid}/{wav_local.name}")
            if r2_url:
                result["wav_url"] = r2_url
    return result


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

    public_base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/") if r2_enabled() else ""
    generated_prefix = f"{public_base}/generated/" if public_base else None
    permanent_prefixes = (
        f"{public_base}/projects/" if public_base else "",
        f"{public_base}/hearted/" if public_base else "",
    )

    def _promote_to_project(src_url: str, dest_name: str) -> str:
        """Move src into projects/{user.id}/{proj.id}/. Local copy preferred, R2 copy as fallback."""
        if not src_url or not r2_enabled():
            return src_url
        if any(p and src_url.startswith(p) for p in permanent_prefixes):
            return src_url
        dest_key = f"projects/{user.id}/{proj.id}/{dest_name}"
        local = _url_to_local_path(src_url)
        if local and local.exists():
            uploaded = upload_to_r2(local, dest_key)
            if uploaded:
                return uploaded
        if generated_prefix and src_url.startswith(generated_prefix):
            copied = copy_within_r2(src_url, dest_key)
            if copied:
                return copied
        return src_url

    saved_ids = []
    for f in body.files:
        midi_name = (f.midi_url or "").split("/")[-1].split("?")[0]
        wav_name = (f.wav_url or "").split("/")[-1].split("?")[0]
        midi_url = _promote_to_project(f.midi_url, midi_name) if f.midi_url else f.midi_url
        wav_url = _promote_to_project(f.wav_url, wav_name) if f.wav_url else f.wav_url

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

    # Persist DAW state — promote any non-permanent clip WAVs into projects/.../daw/
    promoted_daw_state = None
    if body.daw_state and isinstance(body.daw_state, dict):
        daw = dict(body.daw_state)
        clips = list(daw.get("clips") or [])
        if r2_enabled():
            public_base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
            generated_prefix = f"{public_base}/generated/" if public_base else None
            permanent_prefixes = (
                f"{public_base}/projects/" if public_base else "",
                f"{public_base}/hearted/" if public_base else "",
            )
            new_clips = []
            for clip in clips:
                v = dict(clip.get("variation") or {})
                wav_url = v.get("wav_url")
                if wav_url:
                    is_permanent = any(p and wav_url.startswith(p) for p in permanent_prefixes)
                    if not is_permanent:
                        filename = wav_url.split("/")[-1].split("?")[0]
                        dest_key = f"projects/{user.id}/{proj.id}/daw/{filename}"
                        # Local /output/... → upload from disk; R2 generated/... → server-side copy
                        new_url = None
                        if wav_url.startswith("/output/"):
                            wav_local = _url_to_local_path(wav_url)
                            if wav_local and wav_local.exists():
                                new_url = upload_to_r2(wav_local, dest_key)
                        elif generated_prefix and wav_url.startswith(generated_prefix):
                            new_url = copy_within_r2(wav_url, dest_key)
                        if new_url:
                            v["wav_url"] = new_url
                clip = dict(clip)
                clip["variation"] = v
                new_clips.append(clip)
            daw["clips"] = new_clips
        promoted_daw_state = daw
        proj.daw_state = json.dumps(daw)

    db.commit()
    db.refresh(proj)

    return JSONResponse({
        "id": proj.id,
        "name": proj.name,
        "created_at": proj.created_at.isoformat(),
        "file_count": len(body.files),
        "daw_state": promoted_daw_state,
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
# Email open tracking
# ---------------------------------------------------------------------------

_TRANSPARENT_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
    b"\x00\x00\x02\x02D\x01\x00;"
)


def _log_email_event(db, table: str, email: str, ip: str):
    try:
        db.execute(
            text(f"CREATE TABLE IF NOT EXISTS {table} (id SERIAL PRIMARY KEY, email TEXT, ts TIMESTAMPTZ DEFAULT NOW(), ip TEXT)"),
        )
        db.execute(text(f"INSERT INTO {table} (email, ip) VALUES (:email, :ip)"), {"email": email, "ip": ip})
        db.commit()
    except Exception as e:
        print(f"[{table}] db error: {e}")


def _get_email_events(db, table: str):
    try:
        db.execute(text(f"CREATE TABLE IF NOT EXISTS {table} (id SERIAL PRIMARY KEY, email TEXT, ts TIMESTAMPTZ DEFAULT NOW(), ip TEXT)"))
        db.commit()
        rows = db.execute(text(f"SELECT email, ts, ip FROM {table} ORDER BY ts DESC")).fetchall()
        return [{"email": r[0], "ts": r[1].isoformat(), "ip": r[2]} for r in rows]
    except Exception:
        return []


@app.get("/track/open")
async def track_open(id: str = "", request: Request = None, db=Depends(get_db)):
    import base64
    from fastapi.responses import Response
    try:
        email = base64.urlsafe_b64decode(id + "==").decode()
        ip = request.headers.get("x-forwarded-for", "") if request else ""
        if db is not None:
            _log_email_event(db, "email_opens", email, ip)
        print(f"[email-open] {email}")
    except Exception:
        pass
    return Response(content=_TRANSPARENT_GIF, media_type="image/gif", headers={"Cache-Control": "no-store"})


@app.get("/api/email-opens")
async def get_email_opens(request: Request, db=Depends(get_db)):
    user = get_current_user(request, db) if db is not None else None
    admin_emails = {x.strip().lower() for x in os.environ.get("ADMIN_EMAILS", "").split(",") if x.strip()}
    if not user or user.email.lower() not in admin_emails:
        raise HTTPException(status_code=403, detail="Admin only")
    return JSONResponse(_get_email_events(db, "email_opens") if db is not None else [])


# ---------------------------------------------------------------------------
# Email click tracking
# ---------------------------------------------------------------------------

@app.get("/track/click")
async def track_click(id: str = "", request: Request = None, db=Depends(get_db)):
    import base64
    from fastapi.responses import RedirectResponse
    try:
        email = base64.urlsafe_b64decode(id + "==").decode()
        ip = request.headers.get("x-forwarded-for", "") if request else ""
        if db is not None:
            _log_email_event(db, "email_clicks", email, ip)
        print(f"[email-click] {email}")
    except Exception:
        pass
    return RedirectResponse(url="https://museaimusician.com", status_code=302)


@app.get("/api/email-clicks")
async def get_email_clicks(request: Request, db=Depends(get_db)):
    user = get_current_user(request, db) if db is not None else None
    admin_emails = {x.strip().lower() for x in os.environ.get("ADMIN_EMAILS", "").split(",") if x.strip()}
    if not user or user.email.lower() not in admin_emails:
        raise HTTPException(status_code=403, detail="Admin only")
    return JSONResponse(_get_email_events(db, "email_clicks") if db is not None else [])


# ---------------------------------------------------------------------------
# Admin: user report
# ---------------------------------------------------------------------------

@app.get("/api/admin/users")
async def admin_users(request: Request, db=Depends(get_db)):
    user = get_current_user(request, db) if db is not None else None
    admin_emails = {x.strip().lower() for x in os.environ.get("ADMIN_EMAILS", "").split(",") if x.strip()}
    if not user or user.email.lower() not in admin_emails:
        raise HTTPException(status_code=403, detail="Admin only")
    from core.models import User
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "name": u.name,
            "email": u.email,
            "signed_up": u.created_at.strftime("%Y-%m-%d %H:%M UTC") if u.created_at else None,
            "plan": u.subscription_plan or "free",
            "subscription_status": u.subscription_status,
            "lifetime_generations": u.lifetime_generations or 0,
            "monthly_generations": u.monthly_generations or 0,
        }
        for u in users
    ]


# ---------------------------------------------------------------------------
# PostHog reverse proxy — routes analytics through first-party domain to
# avoid Cloudflare blocking outbound requests to us.i.posthog.com
# ---------------------------------------------------------------------------

@app.get("/api/download")
async def proxy_download(url: str):
    """Proxy a file from R2 through the server to avoid browser CORS restrictions."""
    import httpx
    from fastapi.responses import StreamingResponse as SR
    public_base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    is_r2 = public_base and url.startswith(public_base + "/")
    is_local = url.startswith("/output/")
    if not is_r2 and not is_local:
        raise HTTPException(status_code=400, detail="Invalid download URL")
    print(f"[download] {'r2' if is_r2 else 'local'}: {url.split('/')[-1]}")
    if url.startswith("/output/"):
        # Local file — serve directly
        local_path = OUTPUT_DIR / url[len("/output/"):]
        if not local_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        suffix = local_path.suffix.lower()
        mime = "audio/midi" if suffix in (".mid", ".midi") else "audio/wav"
        return SR(open(local_path, "rb"), media_type=mime,
                  headers={"Content-Disposition": f'attachment; filename="{local_path.name}"'})
    async def stream():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, timeout=30) as resp:
                async for chunk in resp.aiter_bytes(65536):
                    yield chunk
    filename = url.split("/")[-1]
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime = "audio/midi" if suffix in ("mid", "midi") else "audio/wav"
    return SR(stream(), media_type=mime,
              headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.api_route("/ingest/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def posthog_proxy(path: str, request: Request):
    import httpx
    target = f"https://us.i.posthog.com/{path}"
    params = dict(request.query_params)
    body = await request.body()
    headers = {
        "content-type": request.headers.get("content-type", "application/json"),
    }
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=target,
            params=params,
            content=body,
            headers=headers,
            timeout=10,
        )
    if resp.status_code == 204 or not resp.content:
        return Response(status_code=resp.status_code)
    try:
        content = resp.json()
    except Exception:
        content = {}
    return JSONResponse(content=content, status_code=resp.status_code)


# ---------------------------------------------------------------------------
# Nasty — AI-native DAW (prompt-driven song building)
# ---------------------------------------------------------------------------

import anthropic as _nasty_anthropic

_NASTY_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "nasty_system.md").read_text()
_NASTY_PERSONAL_DEFAULTS = (Path(__file__).parent / "prompts" / "personal_defaults.md").read_text()


# Load the community plugin-knowledge registry. Each markdown file is one
# plugin cheatsheet — where its presets live, notable params, quirks. Matched
# by frontmatter `name:` against the user's actually-installed plugin manifest,
# so Claude only sees entries for plugins that are on THIS user's machine.
# The registry is a plain-markdown git-versioned folder — the whole point is
# that it's community-maintained and shareable across users, not a per-user
# thing that has to be re-researched every launch.
_PLUGIN_KNOWLEDGE_DIR = Path(__file__).parent / "plugin-knowledge"
_PLUGIN_SHEETS_DIR = _PLUGIN_KNOWLEDGE_DIR / "plugins"
_SOUND_GOALS_DIR = _PLUGIN_KNOWLEDGE_DIR / "sound-goals"


def _load_plugin_knowledge() -> tuple[dict[str, str], dict[str, dict]]:
    # Per-plugin execution-layer sheets. Keyed by lowercase plugin name.
    # Matched against the user's installed plugin manifest so Claude only
    # sees entries for plugins actually on this machine.
    entries: dict[str, str] = {}
    parsed: dict[str, dict] = {}
    if not _PLUGIN_SHEETS_DIR.is_dir():
        return entries, parsed
    for md in _PLUGIN_SHEETS_DIR.glob("*.md"):
        if md.name.lower() == "readme.md":
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except Exception:
            continue
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)
        name_match = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        key = name.lower()
        entries[key] = content
        # Extract the first paragraph after the H1 heading as a short summary
        # for the on-demand lightweight index. This is what Claude sees on
        # every message — the full cheatsheet ships only when it calls the
        # `get_plugin_cheatsheet` tool for a specific plugin.
        body_after_fm = content[m.end():]
        summary = ""
        first_para = re.search(r"^# .+?\n\n(.+?)(?:\n\n|\Z)", body_after_fm, re.DOTALL)
        if first_para:
            summary = " ".join(first_para.group(1).split())  # collapse whitespace
        # Pull structured `preset_paths` (list under the yaml key). Each entry
        # is "<dir>:<ext>" — one directory to scan recursively, one extension
        # to match. Client-side (Electron) does the actual disk walk.
        preset_paths: list[str] = []
        pp_match = re.search(
            r"^preset_paths:\s*\n((?:  - .+\n?)+)", fm, re.MULTILINE)
        if pp_match:
            for line in pp_match.group(1).splitlines():
                s = line.strip()
                if s.startswith("- "):
                    preset_paths.append(s[2:].strip().strip('"').strip("'"))
        parsed[key] = {"name": name, "preset_paths": preset_paths, "summary": summary}
    return entries, parsed


def _load_sound_goals() -> dict[str, str]:
    # Discovery-layer sheets organized by sound goal (Reverbs, Bass, Pads,
    # etc.). Returned as a dict keyed by lowercase category name (e.g.
    # "reverbs", "bass") so the chat handler can pick only the categories
    # the user asked about instead of shipping the whole library on every
    # message. Full library ≈ 16K tokens, single category ≈ 1-2K tokens.
    sheets: dict[str, str] = {}
    if not _SOUND_GOALS_DIR.is_dir():
        return sheets
    for md in sorted(_SOUND_GOALS_DIR.rglob("*.md")):
        try:
            content = md.read_text(encoding="utf-8")
        except Exception:
            continue
        # Category key is the filename stem, lowercase.
        sheets[md.stem.lower()] = content
    return sheets


# Simple keyword → sound-goal-category routing. Kept intentionally shallow;
# a fancier classifier would burn tokens/cost more than it saves. When the
# user's message hits multiple categories we ship all of them — cheap
# compared to shipping all 20.
_SOUND_GOAL_KEYWORDS: dict[str, list[str]] = {
    "reverbs":     ["reverb", "verb", "hall", "room", "plate", "shimmer",
                    "cathedral", "space", "ambien"],
    "delays":      ["delay", "echo", "slap", "dub", "throw"],
    "compression": ["compress", "punch", "glue", "sidechain", "duck",
                    "squash", "attack", "release", "limiter"],
    "eq":          ["eq", " boost", "notch", "high pass", "low pass",
                    "hipass", "lopass", "highpass", "lowpass"],
    "saturation":  ["satur", "distort", "warm", "tape", "tube", "grit",
                    "drive", "crunch", "overdrive", "fuzz"],
    "modulation":  ["chorus", "flang", "phaser", "phase", "ensemble",
                    "vibrato", "modulat"],
    "stereo":      ["stereo", "wide", "width", " pan", "mono"],
    "pitch":       ["pitch", "autotune", "auto-tune", "tune vocal",
                    "octaver", "harmoniz"],
    "filters":     ["filter", "cutoff", "resonance", "wah"],
    "utility":     ["gain stag", "trim", "volume balance", "level"],
    "bass":        ["bass", "sub ", " 808"],
    "lead":        ["lead", "melody"],
    "pads":        ["pad", "atmos"],
    "drums":       ["drum", "kick", "snare", "hi-hat", "hihat", "hat",
                    "cymbal", "percussion", "beat"],
    "vocal":       ["vocal", " vox", "singer", "voice"],
    "strings":     ["string", "violin", "viola", "cello", "orchestra"],
    "keys":        ["piano", "rhodes", "wurli", "organ", "keys"],
    "winds":       ["flute", "clarinet", "sax ", "saxophone", "oboe",
                    "bassoon", "trumpet", "brass"],
    "world":       ["tabla", "sitar", "world", "ethnic", "koto"],
    "textures":    ["texture", "glitch", "noise", "granul", "atmospher"],
}


def _pick_sound_goal_categories(user_message: str) -> list[str]:
    """Return the lowercase categories relevant to this message. Empty
    list = no match; the caller ships nothing (Claude falls back on its
    own musical knowledge — fine for the common tool-focused turns like
    'set BPM to 90' or 'delete pattern 2')."""
    m = (user_message or "").lower()
    matched: list[str] = []
    for cat, keywords in _SOUND_GOAL_KEYWORDS.items():
        if any(kw in m for kw in keywords):
            matched.append(cat)
    return matched


# Cached at module import — Railway redeploys on every push, so cache
# lifetime = deploy lifetime. That's the right freshness knob.
_PLUGIN_KNOWLEDGE, _PLUGIN_KNOWLEDGE_PARSED = _load_plugin_knowledge()
_SOUND_GOALS = _load_sound_goals()


# Persistent gap log — plugins users have on their machines that we don't
# have a cheatsheet for yet. Written to disk (Railway ephemeral, but the
# batched research script drains it every run before the next redeploy).
_GAP_LOG_PATH = Path("/tmp/nasty-plugin-gaps.jsonl")


def _log_plugin_gaps(plugins: list) -> None:
    if not plugins:
        return
    missing = []
    for p in plugins:
        if not isinstance(p, dict):
            continue
        name = (p.get("name") or "").strip()
        if not name:
            continue
        if name.lower() in _PLUGIN_KNOWLEDGE:
            continue
        missing.append({
            "name": name,
            "manufacturer": p.get("manufacturer") or "",
            "format": p.get("format") or "",
            "is_instrument": p.get("isInstrument"),
        })
    if not missing:
        return
    # Append newline-delimited JSON — trivial to parse from the research
    # script, cheap to write, no db dependency.
    import time
    try:
        with _GAP_LOG_PATH.open("a", encoding="utf-8") as f:
            for m in missing:
                f.write(json.dumps({**m, "ts": int(time.time())}) + "\n")
    except Exception:
        pass


@app.get("/nasty/plugin-knowledge")
def nasty_plugin_knowledge():
    # Renderer fetches this on startup to know which of the user's installed
    # plugins have preset_paths on disk it should scan. Returned as a dict
    # keyed by the lowercase plugin name so the client can look up by
    # manifest name directly.
    return _PLUGIN_KNOWLEDGE_PARSED


class NastyStaleReport(BaseModel):
    name: str
    manufacturer: str = ""
    format: str = ""
    reason: str = "preset_paths_empty"  # extensible for other failure modes later


@app.post("/nasty/plugin-knowledge-stale")
def nasty_plugin_knowledge_stale(req: NastyStaleReport):
    # Client-side signal: "I scanned this plugin's declared preset_paths and
    # got zero files, so the cheatsheet is probably wrong." Gets added to the
    # same gap log as missing plugins, but with `stale: true` so the research
    # script knows to REPLACE the existing entry instead of skipping it.
    import time
    try:
        with _GAP_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "name": req.name.strip(),
                "manufacturer": req.manufacturer,
                "format": req.format,
                "stale": True,
                "reason": req.reason,
                "ts": int(time.time()),
            }) + "\n")
    except Exception:
        pass
    return {"ok": True}


# Bundle manifest — the curated list of free plugins + sample content Nasty
# offers new users during onboarding. Loaded at module init so we don't hit
# the disk on every request; the file changes rarely and only on redeploy.
_BUNDLE_MANIFEST_PATH = Path(__file__).parent / "nasty-bundle.json"
try:
    _BUNDLE_MANIFEST = json.loads(_BUNDLE_MANIFEST_PATH.read_text(encoding="utf-8"))
except Exception:
    _BUNDLE_MANIFEST = {"plugins": [], "sound_content": [], "bundles": {}}


@app.get("/nasty/bundle-manifest")
def nasty_bundle_manifest():
    # Renderer fetches this during onboarding to build the plugin-checkbox
    # UI. Everything here is public info (download URLs, plugin names) —
    # not a secret, just centralized so the manifest can be updated by
    # editing one file in the repo.
    return _BUNDLE_MANIFEST


@app.get("/nasty/plugin-gaps")
def nasty_plugin_gaps():
    # Maintainer endpoint — dumps the currently-logged gap entries so the
    # batched research script can be pointed at production. Not a secret
    # (only plugin names + counts), but not linked from anywhere either.
    if not _GAP_LOG_PATH.exists():
        return {"entries": []}
    entries: list[dict] = []
    try:
        for line in _GAP_LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass
    return {"entries": entries}


# In-memory throttle timestamp — last time we fired the research workflow.
# Reset on server redeploy, which is fine: Railway redeploys are rare
# enough that this doesn't leak the throttle window across restarts in
# any meaningful way.
_LAST_RESEARCH_TRIGGER_TS: dict[str, float] = {"ts": 0.0}
_RESEARCH_THROTTLE_SECONDS = 3600  # 1 hour


@app.post("/nasty/trigger-research")
def nasty_trigger_research():
    """Fires the GitHub Actions research workflow on demand.

    Called by the client during onboarding (and any time the client wants
    to force a research pass instead of waiting for the daily cron).
    Throttled to once per hour so a client bug can't spam workflow runs.

    Requires GITHUB_RESEARCH_TOKEN env var — a fine-grained personal-access
    token with `actions: write` on the midi-generator repo. If unset, the
    endpoint returns a soft no-op so onboarding still succeeds.
    """
    import time
    import urllib.request
    import urllib.error

    token = os.getenv("GITHUB_RESEARCH_TOKEN", "").strip()
    if not token:
        return {
            "ok": False,
            "reason": "GITHUB_RESEARCH_TOKEN not set on server — "
                      "research will run on the daily cron instead",
        }

    now = time.time()
    since_last = now - _LAST_RESEARCH_TRIGGER_TS["ts"]
    if since_last < _RESEARCH_THROTTLE_SECONDS:
        # Not an error — the plugins are still in the gap log and will be
        # picked up on the next allowed fire (or the daily cron). Just tell
        # the client we intentionally skipped.
        return {
            "ok": True,
            "fired": False,
            "reason": f"throttled — last fire was {int(since_last)}s ago",
            "next_available_in": int(_RESEARCH_THROTTLE_SECONDS - since_last),
        }

    # GitHub REST: POST /repos/{owner}/{repo}/actions/workflows/{file}/dispatches
    # requires `ref` in the body — main branch is the workflow's home.
    url = ("https://api.github.com/repos/lynch-brendan/midi-generator"
           "/actions/workflows/research-plugin-gaps.yml/dispatches")
    body = json.dumps({"ref": "main"}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "nasty-server/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            # 204 No Content on success. Anything 2xx is fine.
            if 200 <= resp.status < 300:
                _LAST_RESEARCH_TRIGGER_TS["ts"] = now
                return {"ok": True, "fired": True, "status": resp.status}
            return {"ok": False, "reason": f"github returned {resp.status}"}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "reason": f"github http {exc.code}: {exc.reason}"}
    except Exception as exc:
        return {"ok": False, "reason": f"error: {exc}"}

_NASTY_TOOLS = [
    {
        "name": "set_tempo",
        "description": "Set the song's tempo in BPM.",
        "input_schema": {
            "type": "object",
            "properties": {"bpm": {"type": "number"}},
            "required": ["bpm"],
        },
    },
    {
        "name": "play",
        "description": (
            "Start transport playback (equivalent to hitting the Play button). "
            "Plays in whatever mode is currently active (PAT loops the current "
            "pattern; SONG plays the whole arrangement). Optionally set the "
            "mode first via set_transport_mode."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "stop",
        "description": "Stop transport playback (equivalent to hitting the Stop button).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "set_transport_mode",
        "description": (
            "Switch between pattern-loop mode ('pat' — loops the current "
            "pattern) and song mode ('song' — plays the full arrangement "
            "in the playlist)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": ["pat", "song"]}},
            "required": ["mode"],
        },
    },
    {
        "name": "start_recording",
        "description": (
            "Start recording audio into a new take clip. Automatically "
            "switches the transport to SONG mode and rolls playback so the "
            "take lands on the arrangement at the current transport "
            "position. Requires the user to have already routed a mic to a "
            "mixer bus (via the mixer's IN button). If no mic is routed, "
            "the tool will return an error telling the user to do that "
            "first. The user can end the take by hitting the stop button "
            "or asking you to call stop_recording (voice PTT works mid-take)."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "stop_recording",
        "description": (
            "Stop the current audio take. The engine finalises the WAV and "
            "drops the take as an audio clip on the arrangement at the "
            "position where recording started."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "keep_idea",
        "description": (
            "When the Ideas Panel is open, promote one of the on-screen "
            "ideas to a permanent channel + arrangement clip. Match by "
            "`name` (fuzzy substring, case-insensitive — 'morning light' "
            "matches 'Morning Light Chords') OR by 1-based `index`. Use "
            "when the user says 'keep the X one' or 'I like number 2.'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name":  {"type": "string"},
                "index": {"type": "integer"},
            },
        },
    },
    {
        "name": "close_ideas_panel",
        "description": (
            "Close the Ideas Panel and stop the auto-cycle audition. Use "
            "when the user says 'close the panel,' 'stop cycling,' 'never "
            "mind,' or asks for something unrelated after ideas were up."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "save_song",
        "description": (
            "Save the current song as a JSON file. Triggers a browser "
            "download of nasty-song.json — the user's browser will prompt "
            "them to pick a location. Use this whenever the user asks to "
            "save / export their project."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "new_song",
        "description": (
            "Start a fresh empty project. Clears all channels, patterns, "
            "playlist clips, and chat history. Use only when the user "
            "explicitly asks to start over / new song / clear everything. "
            "Their current work is lost unless they saved first."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "load_drum_kit",
        "description": (
            "Swap the samples on the four built-in drum channels (ch_kick, "
            "ch_snare, ch_hh, ch_clap) to a vintage drum-machine kit. Pick "
            "`name` from the drum-kits list shipped in the system context. "
            "Fuzzy substring match — 'TR-808' hits 'Roland TR-808', 'MPC' "
            "hits 'Akai MPC-2000'. Use this instead of creating new drum "
            "channels — the four channels already exist; you're just changing "
            "their sound. Guidance for kit selection (trap → TR-808, boom-bap "
            "→ MPC60, 80s pop → Linn LM1, house → Roland f30, lo-fi → RZ-1, "
            "cinematic → Fairlight IIx) lives in the personal defaults file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "create_channel",
        "description": (
            "Create a new channel in the Channel Rack. A channel is one sound "
            "(instrument). Notes reference channels by id. You invent the id "
            "(short lowercase slug like `kick`, `bass`, `lead`)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "instrument": {
                    "type": "string",
                    "enum": ["piano", "bass", "lead", "pad", "drums"],
                },
                "volume": {"type": "number"},
            },
            "required": ["id", "name", "instrument"],
        },
    },
    {
        "name": "delete_channel",
        "description": "Delete a channel and all notes tagged to it in every pattern.",
        "input_schema": {
            "type": "object",
            "properties": {"channel_id": {"type": "string"}},
            "required": ["channel_id"],
        },
    },
    {
        "name": "set_channel_volume",
        "description": "Set a channel's volume (0-1).",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "volume": {"type": "number"},
            },
            "required": ["channel_id", "volume"],
        },
    },
    {
        "name": "load_gm_instrument",
        "description": (
            "Create a channel using a General MIDI program from the bundled "
            "SoundFont. Use this when the user asks for a realistic instrument "
            "by name (piano, trumpet, violin, flute, cello, guitar, organ, "
            "harp, brass, strings, choir, etc.) — GM has 128 canonical programs "
            "and they sound like the real instrument. Cheaper and more reliable "
            "than trying to coax a subtractive synth into being a trumpet. "
            "`gm_program` is 0-127 (0=Acoustic Grand Piano, 40=Violin, 56=Trumpet, "
            "73=Flute, etc. — you know GM). YOU invent `channel_id` (short slug "
            "like `trumpet`, `piano`) — use the same id in create_pattern notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "channel_name": {"type": "string"},
                "gm_program": {"type": "integer", "minimum": 0, "maximum": 127},
            },
            "required": ["channel_id", "channel_name", "gm_program"],
        },
    },
    {
        "name": "load_instrument",
        "description": (
            "Create a new channel and load a VST3/AU instrument plugin onto it. "
            "Use for user requests like 'put a synth on channel 2', 'add Serum', "
            "'give me a Rhodes'. Pick a `plugin_id` from the Installed plugins "
            "manifest — MUST be a plugin with isInstrument=true. YOU invent both "
            "`channel_id` (short lowercase slug like `bass`, `lead`, `pluck` — "
            "same convention as create_channel) AND `channel_name` (display "
            "label). Use the same `channel_id` when writing notes for this "
            "channel in the same turn's create_pattern call — otherwise the "
            "notes reference a channel that doesn't exist and the pattern is "
            "silent. Do not use this for effects — those go through "
            "add_plugin_effect. Optionally pass `preset_name` (must match one "
            "of the entries in the plugin's `presets` array from the manifest) "
            "to load a specific patch at the same time. Fuzzy substring match "
            "— 'wobble' hits 'Wobble Bass'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "channel_name": {"type": "string"},
                "plugin_id": {"type": "string"},
                "preset_name": {"type": "string"},
            },
            "required": ["channel_id", "channel_name", "plugin_id"],
        },
    },
    {
        "name": "add_plugin_effect",
        "description": (
            "Add a VST3/AU effect plugin onto an existing channel's effect chain. "
            "Use for 'add reverb to chords', 'put a compressor on the bass', etc. "
            "Pick a `plugin_id` from the Installed plugins manifest — MUST have "
            "isInstrument=false. Channel must already exist. Optionally pass "
            "`preset_name` from the plugin's `presets` array to select a specific "
            "factory preset (e.g. 'Cathedral' for a reverb)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "plugin_id": {"type": "string"},
                "preset_name": {"type": "string"},
            },
            "required": ["channel_id", "plugin_id"],
        },
    },
    {
        "name": "set_plugin_param",
        "description": (
            "Tweak a single parameter on a loaded plugin. Use this for 'turn "
            "down the reverb' (target the reverb's Wet/Mix param), 'make the "
            "filter darker' (Cutoff param on the synth), 'more decay' (Decay/"
            "Time param), etc. `owner_id` is the id of the channel (to tweak "
            "its instrument) OR the mixer bus (to tweak an effect on the bus). "
            "`slot_id` empty targets the instrument; non-empty targets the "
            "effect slot with that id. `param_name` is fuzzy-matched (case-"
            "insensitive substring) against the plugin's param list — see "
            "`params` on song.channels[*] (instrument) or on "
            "song.channels[*].effects[*] / song.mixer.busses[*].effects[*]. "
            "`value` is 0.0-1.0 in normalised parameter space (0 = min, "
            "1 = max). For 'turn it down' start around 0.3; 'make it huge' "
            "around 0.85. Preferable to remove+re-add whenever the user just "
            "wants to nudge something they already have."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner_id": {"type": "string"},
                "slot_id": {"type": "string"},
                "param_name": {"type": "string"},
                "value": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["owner_id", "param_name", "value"],
        },
    },
    {
        "name": "remove_plugin_effect",
        "description": (
            "Remove a specific plugin effect slot. Use when the user asks to "
            "delete/clear an existing effect, or when you want to replace one "
            "effect with another (remove then add). `owner_id` is the id of the "
            "channel or mixer bus that owns the slot — look at song.channels[*] "
            "and song.mixer.busses[*] for effects[*].slotId. `slot_id` is the "
            "slotId string of the effect to remove."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner_id": {"type": "string"},
                "slot_id": {"type": "string"},
            },
            "required": ["owner_id", "slot_id"],
        },
    },
    {
        "name": "sidechain_channel",
        "description": (
            "Route one channel/bus's signal into another bus's sidechain input. "
            "Classic use: 'sidechain the kick to the bass' → every kick hit "
            "ducks the bass ('pump'). Requires a sidechain-capable compressor "
            "already loaded on the TARGET bus (e.g. Fruity Limiter, OTT, most "
            "Airwindows / Klanghelm compressors). If no compressor is loaded, "
            "add one first via add_plugin_effect on the target's mixer bus, "
            "then call this. "
            "`source_id` = the channel that TRIGGERS ducking (usually a kick — "
            "can be a channel id like 'ch_kick' OR a bus id like 'bus_1'; if a "
            "channel is given we route from the bus it's on). "
            "`target_id` = the bus id whose compressor SHOULD DUCK (like 'bus_2'). "
            "Pass empty target_id to remove an existing sidechain from source."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string"},
                "target_id": {"type": "string"},
            },
            "required": ["source_id", "target_id"],
        },
    },
    {
        "name": "apply_effect",
        "description": (
            "Add or update an effect on a channel. "
            "compressor params: {threshold, ratio, attack, release}. "
            "reverb params: {wet: 0-1, decay: seconds 0.5-4}. "
            "delay params: {time: seconds 0.05-1, feedback: 0-0.8, wet: 0-1}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "effect": {"type": "string", "enum": ["compressor", "reverb", "delay"]},
                "params": {"type": "object"},
            },
            "required": ["channel_id", "effect"],
        },
    },
    {
        "name": "remove_effect",
        "description": "Remove an effect from a channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "effect": {"type": "string"},
            },
            "required": ["channel_id", "effect"],
        },
    },
    {
        "name": "create_pattern",
        "description": (
            "Create a pattern. A pattern is a block of notes that can contain notes "
            "for MULTIPLE channels at once (e.g. one pattern with kick + snare + bass + "
            "chords). You invent the pattern id (e.g. `verse`, `chorus`). Each note is "
            "{channel_id, pitch, start_beat, duration_beats, velocity}. 1 bar = 4 beats. "
            "start_beat is beats from the pattern start (not the song start)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "length_bars": {"type": "number"},
                "notes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string"},
                            "pitch": {"type": "number"},
                            "start_beat": {"type": "number"},
                            "duration_beats": {"type": "number"},
                            "velocity": {"type": "number"},
                        },
                        "required": ["channel_id", "pitch", "start_beat", "duration_beats"],
                    },
                },
            },
            "required": ["id", "name", "length_bars", "notes"],
        },
    },
    {
        "name": "edit_pattern",
        "description": (
            "REPLACES all notes in an existing pattern with the ones you pass in. "
            "Use this ONLY when the user wants to rewrite the whole pattern (e.g. "
            "'make this simpler', 'redo it in D minor'). If they want to ADD a part "
            "on top of what's already there (e.g. 'add hihats to this'), use "
            "`add_pattern_notes` instead — otherwise you will wipe the existing parts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern_id": {"type": "string"},
                "notes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string"},
                            "pitch": {"type": "number"},
                            "start_beat": {"type": "number"},
                            "duration_beats": {"type": "number"},
                            "velocity": {"type": "number"},
                        },
                        "required": ["channel_id", "pitch", "start_beat", "duration_beats"],
                    },
                },
            },
            "required": ["pattern_id", "notes"],
        },
    },
    {
        "name": "add_pattern_notes",
        "description": (
            "APPEND notes to an existing pattern without touching what's already there. "
            "Use this for 'add hihats to this', 'layer a bass on top', 'add a lead line to "
            "the verse' — anywhere the user wants to KEEP the existing parts and add "
            "something new. Each note needs its own channel_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern_id": {"type": "string"},
                "notes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string"},
                            "pitch": {"type": "number"},
                            "start_beat": {"type": "number"},
                            "duration_beats": {"type": "number"},
                            "velocity": {"type": "number"},
                        },
                        "required": ["channel_id", "pitch", "start_beat", "duration_beats"],
                    },
                },
            },
            "required": ["pattern_id", "notes"],
        },
    },
    {
        "name": "delete_pattern",
        "description": "Delete a pattern and all clips referencing it.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern_id": {"type": "string"}},
            "required": ["pattern_id"],
        },
    },
    {
        "name": "add_pattern_clip",
        "description": (
            "Place a pattern on a playlist track at a bar position. You invent the clip id. "
            "Playlist tracks are pre-created (track_1..track_8) — no need to create them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "track_id": {"type": "string"},
                "pattern_id": {"type": "string"},
                "start_bar": {"type": "number"},
                "length_bars": {"type": "number"},
            },
            "required": ["id", "track_id", "pattern_id", "start_bar"],
        },
    },
    {
        "name": "move_clip",
        "description": "Move a clip to a new bar or track.",
        "input_schema": {
            "type": "object",
            "properties": {
                "clip_id": {"type": "string"},
                "start_bar": {"type": "number"},
                "track_id": {"type": "string"},
            },
            "required": ["clip_id"],
        },
    },
    {
        "name": "delete_clip",
        "description": "Delete a clip by id.",
        "input_schema": {
            "type": "object",
            "properties": {"clip_id": {"type": "string"}},
            "required": ["clip_id"],
        },
    },
    {
        "name": "repeat_clip",
        "description": (
            "Repeat a pattern-clip N times back-to-back after the original. Each copy references "
            "the SAME pattern, placed at startBar + lengthBars * i. Cheap way to build sections."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "clip_id": {"type": "string"},
                "times": {"type": "integer", "minimum": 1, "maximum": 32},
            },
            "required": ["clip_id", "times"],
        },
    },
    {
        "name": "get_plugin_cheatsheet",
        "description": (
            "Fetch the full cheatsheet for a specific plugin the user has "
            "installed. Call this BEFORE loading, tuning, or picking presets "
            "for a plugin — the cheatsheet lists modes, params, quirks, and "
            "how to control it from chat. Use the plugin's `name` from the "
            "plugin cheatsheet index in the system prompt (e.g. "
            "'ValhallaSupermassive', 'MJUCjr')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The plugin's name as shown in the index (case-insensitive).",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "run_phase1_flex_test",
        "description": (
            "Phase 1 automation experiment for the FLEX preset-priming loop. "
            "Sends MIDI Program Change [0, 5, 20, 100, 5] to the loaded FL "
            "Studio AU channel, snapshots state after each, and reports "
            "back: (1) are all 5 captures distinct, (2) do the two pc(5) "
            "match (deterministic), (3) do plaintext strings inside each "
            "state look like FLEX preset names. Dumps the raw state chunks "
            "to the scratch dir for post-hoc inspection. Fire this when "
            "Brendan says 'run phase 1', 'test the automation', or similar. "
            "No user input required — resolves the FL Studio channel "
            "automatically. Takes ~5 seconds."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Optional — overrides auto-resolved FL Studio channel."},
                "sequence":   {"type": "array",  "items": {"type": "integer"}, "description": "Optional program-change sequence. Defaults to [0, 5, 20, 100, 5]."},
                "delay_ms":   {"type": "integer", "description": "Optional ms between program-change and snapshot. Default 800."},
            },
        },
    },
    {
        "name": "save_current_preset",
        "description": (
            "Capture the current plugin state on a channel and file it in "
            "the user's preset vault under `preset_name`. Use when the user "
            "has browsed to a specific sound inside a plugin's own browser "
            "(e.g. FL Studio AU → FLEX → 'Hard 808s → 808 Aggy', Serato → "
            "a loaded sample, Serum → a wavetable) and wants to save it so "
            "they can re-load it by name later without repeating the "
            "browse. After capture, `load_captured_preset(preset_name)` "
            "spins up a fresh channel with the exact same plugin + state. "
            "Channel resolves in this priority: explicit `channel_id` → "
            "currently-armed channel → most-recently-added plugin channel. "
            "`notes` (optional) shows in the vault index so the user can "
            "remember what a preset sounds like."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "preset_name": {"type": "string"},
                "channel_id": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["preset_name"],
        },
    },
    {
        "name": "load_captured_preset",
        "description": (
            "Spin up a fresh channel with a plugin loaded from the user's "
            "preset vault — the plugin state at capture time is restored, "
            "so if the user captured FL Studio AU with '808 Aggy' selected "
            "inside FLEX, this loads a channel that already sounds like "
            "808 Aggy without any further browsing. Use `preset_name` "
            "exactly as it appears in the vault index shipped in the "
            "system context (case-insensitive match)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "preset_name": {"type": "string"},
            },
            "required": ["preset_name"],
        },
    },
    {
        "name": "list_flex_presets",
        "description": (
            "List presets from the user's FLEX preset library. Use when the "
            "user asks what sounds they have in FLEX ('what bass sounds do "
            "I have?', 'show me lo-fi patches', 'what's in the retrowave "
            "pack?'). The FLEX preset index (pack names + counts) ships in "
            "the system context; this tool returns the actual preset names. "
            "Filter by exact `pack` name, or a `query` substring that "
            "matches either the pack name or a preset name (case-insensitive). "
            "`limit` caps results — default 40, max 200. Returns a plain-text "
            "list grouped by pack. FLEX is loadable via `load_plugin` like "
            "any other VST3."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pack": {
                    "type": "string",
                    "description": "Exact pack name (from the index) to list. Optional.",
                },
                "query": {
                    "type": "string",
                    "description": "Substring to filter preset OR pack names by. Optional.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "description": "Max presets to return. Default 40.",
                },
            },
        },
    },
    {
        "name": "suggest_midi_ideas",
        "description": (
            "Open the Ideas Panel with a few MIDI ideas (chord progression, "
            "bass line, melody, lead, or pad) for the user to audition + "
            "pick. Use this ANY time the user asks for options / ideas / "
            "a few / suggestions on a musical part — 'give me some chord "
            "ideas,' 'make me a couple basslines,' 'suggest a lead,' "
            "'ideas for a pad,' 'what melodies would fit.' Ideas stream in "
            "one at a time (~2-3 s to first idea) and audition alongside "
            "the current song on a preview channel; Keep drops the picked "
            "one onto a new channel + pattern + clip; Close tears it down. "
            "You DO NOT need to also call `load_gm_instrument` / "
            "`create_pattern` / `add_pattern_clip` — the Keep flow handles "
            "channel + pattern + clip creation for you."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "Musically vivid direction — 'warm nostalgic pop "
                        "progression in the vein of early Coldplay,' 'gritty "
                        "808 sub with sidechain feel,' 'melancholy lead in "
                        "the vein of Aphex Twin.' Quality of the ideas "
                        "tracks the vividness of this prompt."
                    ),
                },
                "kind": {
                    "type": "string",
                    "enum": ["chords", "bass", "melody", "lead", "pad", "drums"],
                    "description": (
                        "Which musical part the user wants ideas for. "
                        "Defaults to 'chords' if omitted. 'bass' for "
                        "basslines, 'melody' for top-line melodies, 'lead' "
                        "for synth-lead lines, 'pad' for sustained "
                        "textures, 'drums' for kick/snare/hat patterns "
                        "(client routes by pitch to Nasty's per-piece "
                        "drum channels — you emit MIDI pitches 36 kick, "
                        "38 snare, 42/46 hats, 39 clap)."
                    ),
                },
                "key":    {"type": "string"},
                "tempo":  {"type": "integer"},
                "bars":   {"type": "integer", "enum": [1, 2, 4, 8]},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "try_effects",
        "description": (
            "Open the Ideas Panel with a few effect-plugin options for the "
            "user to A/B on a channel or mixer bus. Use for exploratory "
            "effect asks: 'give me some reverb options,' 'try a few delays "
            "on the vocal,' 'what compressors would work here,' 'suggest "
            "some saturators.' YOU pick the plugins from the Installed "
            "plugins manifest — MUST be `isInstrument: false`. For each, "
            "pick a `preset_name` from that plugin's `presets` array in "
            "the manifest that matches the vibe the user asked for — that "
            "way each audition lands at a *musical* setting instead of the "
            "plugin's raw default (which is often dry / subtle / silent). "
            "Span the vibe range across your picks (for reverbs: one "
            "plate, one hall, one shimmer, one spring, one weird — each "
            "with a matching preset). The Ideas Panel loads them one at a "
            "time onto the target so the user hears each in-DAW alongside "
            "the song; Keep leaves the picked one loaded, Close removes it "
            "and restores the prior state. `target_id` is the channel id "
            "(the client resolves to the channel's mixer bus the same way "
            "`add_plugin_effect` does)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_id": {"type": "string"},
                "plugins": {
                    "type": "array",
                    "description": (
                        "Array of {plugin_id, preset_name?} objects. Pick "
                        "3-5 effect plugins spanning the vibe range. Each "
                        "MUST reference an `isInstrument: false` plugin "
                        "from the manifest; `preset_name` (optional but "
                        "STRONGLY encouraged) should be a real entry from "
                        "that plugin's `presets` array — omit only if the "
                        "plugin has no presets exposed."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "plugin_id":   {"type": "string"},
                            "preset_name": {"type": "string"},
                        },
                        "required": ["plugin_id"],
                    },
                    "minItems": 2,
                    "maxItems": 8,
                },
            },
            "required": ["target_id", "plugins"],
        },
    },
]


class NastyChatRequest(BaseModel):
    song: dict
    message: str
    history: list = []
    plugins: list = []  # engine-scanned VST3/AU manifest
    ideas_panel: dict | None = None  # populated when the Ideas Panel is on-screen
    drum_kits: list = []  # vintage drum-machine kits scanned locally by main.js
    flex_presets: list = []  # FLEX preset library: [{pack, presets: [name, ...]}] from main.js
    preset_vault: list = []  # user-captured plugin state snapshots: [{name, pluginName, pluginId, notes, capturedAt}]


class NastyMidiIdeasRequest(BaseModel):
    # Free-text musical direction ("dark cinematic minor 7ths," "808 sub
    # bass with sidechain feel," "warm nostalgic pad progression"). The
    # `kind` field biases Muse toward the right voicing/register:
    #   - 'chords' : chord progression / harmony
    #   - 'bass'   : bass line
    #   - 'melody' : lead melodic line
    #   - 'lead'   : lead synth line
    #   - 'pad'    : sustained pad / texture
    #
    # `seed` — optional previous idea (or Kept pattern) whose notes bias
    # this batch toward variations of / complements to it. Set by the
    # "More like this" button in the Ideas Panel. Muse's stream_variations
    # already understands seed_variation; we pass this through unchanged.
    prompt: str
    kind: Optional[str] = "chords"
    key: Optional[str] = None
    tempo: Optional[int] = None
    bars: Optional[int] = None
    seed: Optional[dict] = None


# Haiku 4.5 for chord ideation. ~3-4× faster than Sonnet 4.6, ~5× cheaper.
# Ideas are exploratory (user auditions + picks) so imperfect musicality
# is acceptable — the user has ears. Swap back to Sonnet if quality craters.
_IDEAS_MODEL = "claude-haiku-4-5-20251001"


def _format_chord_idea(var: dict, top_gm_patch: int) -> Optional[dict]:
    """Sanitize one Muse variation into the payload the Ideas Panel expects.
    Returns None if the variation is unusable."""
    try:
        clean = sanitize_variation(var)
        info = extract_variation_info(clean)
    except Exception as e:
        print(f"[nasty-ideas] sanitize failed: {e}", flush=True)
        return None
    gm_patch = int(clean.get("gm_patch", top_gm_patch) or 0)
    bars_val = _infer_bars(clean.get("notes", []), declared=clean.get("bars"))
    return {
        "id":         info.id,
        "name":       info.name,
        "character":  info.character,
        "key":        clean.get("key"),
        "tempo":      info.tempo,
        "bars":       bars_val,
        "note_count": info.note_count,
        "notes":      clean["notes"],
        "gm_patch":   gm_patch,
        "instrument": clean.get("instrument"),
    }


# Kind → hint we prepend to the user's prompt so Muse voices the right
# thing. Ambiguity between kinds (e.g. "bassline" said in the user prompt
# but kind='chords') is resolved in favor of the caller's `kind` — that's
# the authoritative signal from the client dispatch.
_MIDI_KIND_HINTS = {
    "chords": "chord progression",
    "bass":   "bass line",
    "melody": "melody line",
    "lead":   "lead line",
    "pad":    "sustained pad / texture",
    "drums":  "drum pattern (use MIDI 36=kick, 38=snare, 42=closed hat, 46=open hat, 39=clap — the client routes by pitch to Nasty's per-piece drum channels)",
}


def _midi_ideas_prompt(prompt: str, kind: str) -> str:
    hint = _MIDI_KIND_HINTS.get((kind or "chords").lower(), "musical part")
    p = prompt.strip()
    return f"{hint}: {p}"


@app.post("/nasty/midi-ideas")
def nasty_midi_ideas(req: NastyMidiIdeasRequest):
    # Streaming SSE endpoint. Each Muse variation yields as it's parsed
    # from the model's streaming output → the Ideas Panel populates ideas
    # incrementally so the first playable idea lands in ~2-3 s instead
    # of waiting ~10-15 s for the full batch. Also survives Cloudflare's
    # gateway timeout, which killed the old non-streaming call at ~30 s.
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    chord_prompt = _midi_ideas_prompt(req.prompt, req.kind or "chords")

    def event_stream():
        top_gm_patch = 0
        count = 0
        try:
            for event in stream_variations(
                chord_prompt,
                lock_key=req.key or None,
                lock_tempo=int(req.tempo) if req.tempo else None,
                seed_variation=req.seed or None,
                model=_IDEAS_MODEL,
                count=3,
            ):
                etype = event.get("type")
                if etype == "meta":
                    top_gm_patch = int(event.get("gm_patch") or 0)
                    # Meta hint before any idea arrives so the panel can
                    # show the instrument the batch is targeting.
                    yield "data: " + json.dumps({
                        "type": "meta",
                        "instrument": event.get("instrument"),
                        "gm_patch": top_gm_patch,
                    }) + "\n\n"
                elif etype == "variation":
                    idea = _format_chord_idea(event["variation"], top_gm_patch)
                    if idea is None:
                        continue
                    count += 1
                    yield "data: " + json.dumps({"type": "idea", "idea": idea}) + "\n\n"
                elif etype == "done":
                    yield "data: " + json.dumps({"type": "done", "count": count}) + "\n\n"
        except Exception as e:
            # SSE errors surface as an in-band `error` event so the client
            # can render a message in-panel instead of hanging forever on
            # an unclosed stream.
            print(f"[nasty-ideas] stream failed: {e}", flush=True)
            yield "data: " + json.dumps({"type": "error", "detail": str(e)}) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/nasty")
def nasty_page():
    return FileResponse(WEB_DIR / "nasty.html")


@app.post("/nasty/chat")
def nasty_chat(req: NastyChatRequest):
    # Plugin manifest is the source of truth for what's actually installed on
    # this machine — Claude picks from it instead of guessing from training
    # data. Kept separate from song state so it stays stable across turns.
    # Always send the block (with count) so Claude can distinguish "scan not
    # done yet" from "user has no plugins" from "user has N plugins."
    plugins = req.plugins or []
    # Slim the plugin manifest before injecting: keep the identifying fields
    # Claude needs to pick and load a plugin, drop the ballooning `presets`
    # arrays (some plugins expose 100+ preset names — that's the bulk of the
    # manifest size). If Claude needs preset info for a specific plugin it
    # calls get_plugin_cheatsheet, which returns curated per-plugin knowledge
    # including preset paths. Trims typical manifest 5-10K → ~1-2K tokens.
    slim_plugins = []
    for p in plugins:
        if not isinstance(p, dict):
            continue
        slim_plugins.append({
            "id":           p.get("id"),
            "name":         p.get("name"),
            "manufacturer": p.get("manufacturer"),
            "format":       p.get("format"),
            "category":     p.get("category"),
            "isInstrument": p.get("isInstrument"),
        })
    plugin_block = (
        f"Installed plugins (VST3/AU scanned by the engine — count: {len(plugins)}):\n"
        f"```json\n{json.dumps(slim_plugins, indent=2)}\n```\n\n"
    )

    # Drum kits available on this machine. Just names + which pieces each kit
    # has (kick/snare/hats/clap) — no absolute paths, since Claude picks by
    # name and the desktop client resolves to files locally. Keeps the payload
    # under ~10KB even for a 200-kit library.
    drum_kits = req.drum_kits or []
    if drum_kits:
        # One line per kit — kit name + short piece coverage summary. Under
        # 10 KB for 200 kits, cache-friendly. Full mapping stays client-side.
        kit_lines = []
        for k in drum_kits:
            if not isinstance(k, dict):
                continue
            name = k.get("name", "?")
            has = k.get("has") or {}
            pieces = [p for p in ("kick", "snare", "chh", "ohh", "clap") if has.get(p)]
            kit_lines.append(f"- **{name}** — {', '.join(pieces) or 'incomplete'}")
        drum_kits_block = (
            f"Vintage drum-machine kits available on this machine "
            f"({len(kit_lines)} kits). Call `load_drum_kit(name)` to swap the "
            f"samples on ch_kick / ch_snare / ch_hh / ch_clap. Fuzzy match — "
            f"'808' hits 'Roland TR-808', 'MPC' hits 'Akai MPC-2000', etc.\n\n"
            + "\n".join(kit_lines)
            + "\n\n"
        )
    else:
        drum_kits_block = ""

    # FLEX preset library summary. Ship pack-name + count in the always-on
    # context (small — ~1 line per pack). The full preset-name lists live
    # in req.flex_presets and get returned on demand via the
    # list_flex_presets tool, so context stays cost-neutral even with
    # 6000+ presets installed.
    flex_presets = req.flex_presets or []
    if flex_presets:
        total_presets = sum(len(p.get("presets") or []) for p in flex_presets if isinstance(p, dict))
        # Sort by count desc so the biggest packs show first — Claude gets
        # a sense of scale + variety in one glance.
        flex_lines = []
        for p in sorted(flex_presets, key=lambda x: -len(x.get("presets") or []) if isinstance(x, dict) else 0):
            if not isinstance(p, dict):
                continue
            pack = p.get("pack", "?")
            count = len(p.get("presets") or [])
            if count <= 0:
                continue
            flex_lines.append(f"- **{pack}** — {count} presets")
        flex_presets_block = (
            f"FLEX preset library on this machine — {total_presets} presets "
            f"across {len(flex_lines)} packs. Call `list_flex_presets` to "
            f"see actual preset names for a specific pack, filter by keyword, "
            f"or search across the whole library. When the user says 'load "
            f"me some bass sounds from FLEX,' `list_flex_presets(query='bass')` "
            f"or by pack `list_flex_presets(pack='Essential Bass Guitars')` "
            f"is the way in. FLEX is a plugin like any other — load it via "
            f"`load_plugin` first, then use its presets by name.\n\n"
            + "\n".join(flex_lines)
            + "\n\n"
        )
    else:
        flex_presets_block = ""

    # Preset vault — user-captured plugin state snapshots (name + plugin
    # + notes only; the state blob stays client-side and is only touched
    # when load_captured_preset fires). This is the ANSWER to "load me
    # 808 Aggy" style asks: whatever the user browsed to inside a plugin
    # (FL Studio AU → FLEX preset X; Serato → sample Y; Serum → wavetable
    # Z) once got captured here, and can be re-loaded on any channel
    # forever after with the exact same sound.
    vault = req.preset_vault or []
    if vault:
        vault_lines = []
        for e in vault:
            if not isinstance(e, dict): continue
            nm = e.get("name", "?")
            plug = e.get("pluginName") or e.get("pluginId") or "unknown plugin"
            notes = (e.get("notes") or "").strip()
            tail = f" — {notes}" if notes else ""
            vault_lines.append(f"- **{nm}** ({plug}){tail}")
        preset_vault_block = (
            f"Captured preset vault — {len(vault_lines)} plugin state "
            f"snapshots the user has saved on THIS machine. Call "
            f"`load_captured_preset(preset_name)` to spin up a fresh "
            f"channel with the exact state (plugin + inner-preset + "
            f"knob positions) restored. When the user says 'load 808 "
            f"Aggy' or 'give me that Rhodes I captured yesterday,' "
            f"match against this list. To CAPTURE a new one, tell the "
            f"user to browse to the preset inside the loaded plugin, "
            f"then call `save_current_preset(preset_name, channel_id?, "
            f"notes?)`.\n\n"
            + "\n".join(vault_lines)
            + "\n\n"
        )
    else:
        preset_vault_block = (
            "Captured preset vault is empty. When the user opens a "
            "plugin (e.g. FL Studio AU → FLEX), browses to a preset "
            "they like, and asks to save it, call "
            "`save_current_preset(preset_name)` — the plugin's current "
            "state gets captured and can be re-loaded on any future "
            "channel by name via `load_captured_preset`.\n\n"
        )

    # When the Ideas Panel is on-screen, tell Claude what's in it so it can
    # honor requests like "keep the morning light one" or "close the panel."
    ideas_block = ""
    if req.ideas_panel and isinstance(req.ideas_panel, dict):
        items = req.ideas_panel.get("ideas") or []
        if items:
            kind = req.ideas_panel.get("kind", "ideas")
            currently = req.ideas_panel.get("currently_playing_index")
            lines = []
            for it in items:
                marker = " ← CURRENTLY PLAYING" if it.get("index") == currently else ""
                kept = " (already kept)" if it.get("kept") else ""
                lines.append(f"  {it.get('index')}. {it.get('name', '?')}{marker}{kept}")
            ideas_block = (
                f"\n⚠️ Ideas Panel is OPEN ({kind}). On-screen options:\n"
                + "\n".join(lines)
                + "\n\n"
                + "RULES while the panel is open:\n"
                + "- 'keep this' / 'I like this' / 'keep it' → keep_idea with the CURRENTLY PLAYING index. Do NOT generate new ideas.\n"
                + "- 'keep the X one' / 'I like number 2' → keep_idea by name or index.\n"
                + "- 'keep this and loop it 16 bars' → keep_idea (current) + close_ideas_panel + repeat_clip to fill 16 bars.\n"
                + "- ANY request that isn't about picking (e.g. 'loop this 16 bars', 'add drums', 'stop', 'play in song mode') → close_ideas_panel FIRST, then do the request. Never re-fire suggest_midi_ideas while the panel is up unless the user explicitly asks for new options.\n\n"
            )

    # Match community plugin-knowledge entries against the user's installed
    # plugins. Only include entries that correspond to a plugin they actually
    # have. Community-maintained cheatsheets tell Claude where preset files
    # live on disk, notable quirks, common recipes — for plugins where the
    # standard VST3/AU program API doesn't expose the real patch browser.
    # Log any of this user's plugins we don't yet have a cheatsheet for —
    # the batched research script drains this to auto-generate entries.
    _log_plugin_gaps(plugins)

    # Build a LIGHTWEIGHT index of every plugin the user has that we also
    # have a cheatsheet for. One line per plugin: name + short summary.
    # The full cheatsheet ships only when Claude calls the
    # get_plugin_cheatsheet tool for a specific plugin. This drops the
    # per-message context from ~50K tokens to ~15K tokens.
    knowledge_index: list[str] = []
    for p in plugins:
        name = (p.get("name") or "").strip().lower() if isinstance(p, dict) else ""
        if name and name in _PLUGIN_KNOWLEDGE:
            parsed = _PLUGIN_KNOWLEDGE_PARSED.get(name, {})
            display_name = parsed.get("name", name)
            summary = parsed.get("summary", "").strip() or "cheatsheet available"
            knowledge_index.append(f"- **{display_name}** — {summary}")

    # Two-layer knowledge injection:
    # 1. Sound-goal sheets (discovery) — organized by what the user asks for
    #    (Reverbs, Bass, Pads, etc.). Read these first to pick the right
    #    tool for the intent. Same across all users — cache-friendly.
    # 2. Plugin sheets (execution) — how to actually load presets, param
    #    quirks, license limits for the plugins THIS user has installed.
    # Only ship the sound-goal categories the user's message actually
    # asked about. Full library is ~16K tokens on every message; a single
    # matched category is ~1-2K. Empty match = ship nothing (fine for
    # tool-focused turns like "set BPM to 90"). See _pick_sound_goal_categories.
    sound_goals_block = ""
    if _SOUND_GOALS:
        picked = _pick_sound_goal_categories(req.message)
        selected_sheets = [_SOUND_GOALS[c] for c in picked if c in _SOUND_GOALS]
        if selected_sheets:
            sound_goals_block = (
                f"Sound-goal cheatsheets (discovery layer, relevant to this "
                f"message — categories: {', '.join(picked)}). Read these to "
                f"pick the right tool for the musical intent, then call "
                f"get_plugin_cheatsheet for the specific plugin you choose:\n\n"
                + "\n\n===\n\n".join(selected_sheets)
                + "\n\n"
            )

    knowledge_block = ""
    if knowledge_index:
        knowledge_block = (
            "Plugin cheatsheet index (execution layer — plugins on THIS user's "
            "machine that we have detailed cheatsheets for). Each entry is "
            "one-line: pick the right one via the sound-goal layer above, "
            "then call the `get_plugin_cheatsheet` tool with the plugin name "
            "to fetch the full sheet BEFORE loading or tuning it. Only fetch "
            "the sheet when you actually need it — don't preload everything.\n\n"
            + "\n".join(knowledge_index)
            + "\n\n"
        )
    # Strip raw plugin params / opaque plugin state from every channel before
    # sending song state to Claude. A single VST with ~200 params serializes
    # to ~120 kB of {index,name,value} triples — Claude can't reason about
    # raw parameter values, and the base64 pluginState blob is only meaningful
    # to the plugin itself. Once a plugin is loaded it lives in the song
    # forever, so every turn was mailing that dead weight uncached at $3/M
    # input tokens. Curated plugin knowledge already reaches Claude via the
    # get_plugin_cheatsheet tool. See devlog for the diagnostic that found
    # this (per-turn cost dropped ~10× after this trim).
    slim_song = dict(req.song) if isinstance(req.song, dict) else req.song
    if isinstance(slim_song, dict) and isinstance(slim_song.get("channels"), list):
        slim_song["channels"] = [
            {k: v for k, v in c.items() if k not in ("params", "pluginState")}
            if isinstance(c, dict) else c
            for c in slim_song["channels"]
        ]

    # Song state + sound-goals change per message; plugin manifest and
    # cheatsheet index are stable per session. Put the DYNAMIC bits into
    # the user message so the cached system prefix stays cache-hit across
    # turns — that's the whole point of prompt caching.
    user_content = (
        f"Current song state:\n```json\n{json.dumps(slim_song, indent=2)}\n```\n\n"
        + ideas_block
        + sound_goals_block
        + f"User: {req.message}"
    )
    # 1-hour cache TTL (default is 5 minutes). Brendan pauses to listen /
    # think / test between chat messages, and every pause >5 min under the
    # old TTL forced a full cache rewrite (~30K tokens re-billed at cache-
    # write rate). 1h TTL costs 2x per cache-write ($7.50/M vs $3.75/M) but
    # avoids that rewrite for real music-making sessions with think time.
    system_blocks = [
        {"type": "text", "text": _NASTY_SYSTEM_PROMPT},
        # Personal defaults: descriptor → preferred plugin+preset map. Read
        # first when the user asks for a sound. Cached separately so edits to
        # this file don't invalidate the plugin_block cache, and vice versa.
        {
            "type": "text",
            "text": _NASTY_PERSONAL_DEFAULTS,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        },
        {
            "type": "text",
            "text": plugin_block + drum_kits_block + flex_presets_block + preset_vault_block + knowledge_block,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        },
    ]
    # Tools JSON is the other big stable chunk — cache_control on the last
    # tool marks the whole tools list as cacheable.
    tools = [dict(t) for t in _NASTY_TOOLS]
    if tools:
        tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral", "ttl": "1h"}}

    # Truncate history to the last 8 messages. Longer conversations balloon
    # per-turn input cost linearly; 8 is enough for context, more just burns
    # tokens on stale turns.
    trimmed_history = list(req.history)[-8:]
    messages = trimmed_history + [{"role": "user", "content": user_content}]
    client = _nasty_anthropic.Anthropic()

    all_tool_calls: list[dict] = []
    text_parts: list[str] = []
    stop_reason = None
    # Sum token accounting across iterations for the training-corpus log.
    total_in = 0
    total_out = 0
    total_cread = 0
    total_cwrite = 0

    for iter_idx in range(6):
        try:
            resp = client.messages.create(
                # Haiku 4.5 is ~5-10x cheaper than Sonnet post-cache-warmup.
                # Trade-off: weaker on musical judgment ("make this feel like
                # a chorus"), fine on parseable commands ("add reverb"). If
                # output quality degrades in real use, revert to
                # claude-sonnet-4-6 — same interface, one-line swap.
                model="claude-haiku-4-5-20251001",
                # 4000 is plenty for chat replies. Cap prevents runaway output
                # cost on chatty turns; hitting the cap is fine (Claude stops
                # cleanly and the tool-use loop continues).
                max_tokens=4000,
                system=system_blocks,
                tools=tools,
                messages=messages,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Claude error: {e}")

        # Log token + cache stats so we can verify caching is hitting.
        # Prints to Railway logs; grep for "[nasty-chat]" to see hit rate.
        u = getattr(resp, "usage", None)
        if u:
            in_tok = getattr(u, "input_tokens", 0)
            out_tok = getattr(u, "output_tokens", 0)
            cread = getattr(u, "cache_read_input_tokens", 0) or 0
            cwrite = getattr(u, "cache_creation_input_tokens", 0) or 0
            total_in += in_tok
            total_out += out_tok
            total_cread += cread
            total_cwrite += cwrite
            print(
                f"[nasty-chat] iter={iter_idx} in={in_tok} out={out_tok} "
                f"cache_read={cread} cache_write={cwrite}",
                flush=True,
            )

        stop_reason = resp.stop_reason
        turn_tool_uses = []
        for block in resp.content:
            if block.type == "tool_use":
                all_tool_calls.append({"name": block.name, "input": block.input})
                turn_tool_uses.append(block)
            elif block.type == "text" and block.text.strip():
                text_parts.append(block.text)

        if stop_reason != "tool_use" or not turn_tool_uses:
            break

        # Feed tool_results back so Claude can continue chaining.
        # `get_plugin_cheatsheet` is real (returns the actual sheet content);
        # everything else is a synthetic "applied" ack — actual state changes
        # live in the client, we just echo the id back.
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in turn_tool_uses:
            inp = block.input or {}
            if block.name == "get_plugin_cheatsheet":
                plugin_name = str(inp.get("name", "")).strip().lower()
                sheet = _PLUGIN_KNOWLEDGE.get(plugin_name)
                if sheet:
                    result_text = sheet
                else:
                    result_text = (
                        f"No cheatsheet found for '{inp.get('name','')}'. "
                        "Only ask for names shown in the index."
                    )
            elif block.name == "list_flex_presets":
                # Filter the FLEX preset library shipped in this request.
                # No server-side cache — the client always has fresh data,
                # and this way multi-machine users don't cross-contaminate.
                requested_pack = (inp.get("pack") or "").strip().lower()
                query = (inp.get("query") or "").strip().lower()
                limit = int(inp.get("limit") or 40)
                if limit < 1: limit = 1
                if limit > 200: limit = 200
                library = req.flex_presets or []
                matches_by_pack: dict[str, list[str]] = {}
                total_matches = 0
                for pack_entry in library:
                    if not isinstance(pack_entry, dict): continue
                    pack_name = pack_entry.get("pack", "")
                    presets = pack_entry.get("presets") or []
                    if requested_pack and requested_pack != pack_name.lower():
                        continue
                    if query and query in pack_name.lower():
                        # Whole pack matches — include all its presets.
                        matches_by_pack[pack_name] = list(presets)
                        total_matches += len(presets)
                        continue
                    if query:
                        hits = [p for p in presets if query in p.lower()]
                        if hits:
                            matches_by_pack[pack_name] = hits
                            total_matches += len(hits)
                    else:
                        # No query, specific pack requested (or nothing) — dump this pack's presets.
                        matches_by_pack[pack_name] = list(presets)
                        total_matches += len(presets)
                if not matches_by_pack:
                    result_text = (
                        f"No FLEX presets matched (pack={inp.get('pack','')!r}, "
                        f"query={inp.get('query','')!r}). Check the FLEX pack "
                        f"list in the system context — pack names must match exactly."
                    )
                else:
                    lines = [f"FLEX preset matches ({total_matches} total, showing up to {limit}):"]
                    shown = 0
                    for pack_name, presets in matches_by_pack.items():
                        if shown >= limit: break
                        remaining = limit - shown
                        subset = presets[:remaining]
                        lines.append(f"\n**{pack_name}** ({len(presets)} match{'es' if len(presets) != 1 else ''}):")
                        for name in subset:
                            lines.append(f"  - {name}")
                        shown += len(subset)
                    if total_matches > limit:
                        lines.append(f"\n… {total_matches - limit} more matches truncated. Narrow the query or set `limit` higher (max 200).")
                    result_text = "\n".join(lines)
            elif block.name in ("add_track", "add_clip") and "id" in inp:
                result_text = f"applied; id={inp['id']}"
            elif block.name == "suggest_midi_ideas":
                # Ideas Panel is populated by a direct client → /nasty/midi-ideas
                # SSE stream — the tool call itself just signals intent.
                # Kept small so Muse's 5-variation JSON doesn't ride along on
                # every subsequent turn's context.
                kind = (inp.get("kind") or "chords").lower()
                result_text = (
                    f"Ideas Panel opened with 3 {kind} ideas for the user "
                    "to audition and pick — no further tool calls needed on "
                    "your side."
                )
            elif block.name == "try_effects":
                # Effects Ideas Panel opens on the client with the plugin_ids
                # you picked from the manifest. No server work — client
                # swaps the loaded plugin on the target in place per audition.
                result_text = (
                    "Effects Ideas Panel opened with the plugins you picked. "
                    "The user will A/B them and Keep the winner — no further "
                    "tool calls needed on your side."
                )
            else:
                result_text = "applied"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })
        messages.append({"role": "user", "content": tool_results})

    # Log this conversation turn to the DB as training-corpus material.
    # Wrapped in try/except so a DB hiccup can't kill the chat response.
    if SessionLocal is not None:
        try:
            from core.models import NastyChatLog
            plugin_names_csv = ",".join(
                (p.get("name") or "").strip() for p in plugins
                if isinstance(p, dict) and p.get("name")
            )
            with SessionLocal() as db:
                row = NastyChatLog(
                    session_id=getattr(req, "session_id", None),
                    user_message=req.message,
                    ai_text="\n".join(text_parts).strip() or None,
                    tool_calls_json=json.dumps(all_tool_calls) if all_tool_calls else None,
                    song_state_json=json.dumps(req.song) if req.song else None,
                    plugin_names=plugin_names_csv or None,
                    input_tokens=total_in or None,
                    output_tokens=total_out or None,
                    cache_read_tokens=total_cread or None,
                    cache_write_tokens=total_cwrite or None,
                    stop_reason=stop_reason,
                )
                db.add(row)
                db.commit()
        except Exception as e:
            print(f"[nasty-chat] log write failed (non-fatal): {e}", flush=True)

    return {
        "text": "\n".join(text_parts).strip(),
        "tool_calls": all_tool_calls,
        "stop_reason": stop_reason,
    }


# ---------------------------------------------------------------------------
# Static file mounts (must come last)
# ---------------------------------------------------------------------------

app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
