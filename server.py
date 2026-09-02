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

from core.claude_client import stream_variations, stream_thinking
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
        "name": "add_track",
        "description": "Create a new track. You invent the id (short slug).",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "instrument": {
                    "type": "string",
                    "enum": ["piano", "bass", "lead", "pad", "drums"],
                },
            },
            "required": ["id", "name", "instrument"],
        },
    },
    {
        "name": "delete_track",
        "description": "Remove a track and all its clips.",
        "input_schema": {
            "type": "object",
            "properties": {"track_id": {"type": "string"}},
            "required": ["track_id"],
        },
    },
    {
        "name": "add_clip",
        "description": (
            "Add a clip of notes to a track at a bar position. "
            "You invent the clip id. Notes are objects: "
            "{pitch, startBeat, durationBeats, velocity}. 1 bar = 4 beats."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "track_id": {"type": "string"},
                "start_bar": {"type": "number"},
                "length_bars": {"type": "number"},
                "notes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pitch": {"type": "number"},
                            "startBeat": {"type": "number"},
                            "durationBeats": {"type": "number"},
                            "velocity": {"type": "number"},
                        },
                        "required": ["pitch", "startBeat", "durationBeats"],
                    },
                },
            },
            "required": ["id", "track_id", "start_bar", "length_bars", "notes"],
        },
    },
    {
        "name": "edit_clip",
        "description": "Replace the notes in an existing clip.",
        "input_schema": {
            "type": "object",
            "properties": {
                "clip_id": {"type": "string"},
                "notes": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["clip_id", "notes"],
        },
    },
    {
        "name": "move_clip",
        "description": "Move a clip to a new starting bar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "clip_id": {"type": "string"},
                "start_bar": {"type": "number"},
            },
            "required": ["clip_id", "start_bar"],
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
        "name": "apply_effect",
        "description": (
            "Add or update an effect on a track. "
            "compressor params: {}. "
            "reverb params: {wet: 0-1, decay: seconds 0.5-4}. "
            "delay params: {time: seconds 0.05-1, feedback: 0-0.8, wet: 0-1}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "track_id": {"type": "string"},
                "effect": {
                    "type": "string",
                    "enum": ["compressor", "reverb", "delay"],
                },
                "params": {"type": "object"},
            },
            "required": ["track_id", "effect"],
        },
    },
    {
        "name": "remove_effect",
        "description": "Remove an effect from a track.",
        "input_schema": {
            "type": "object",
            "properties": {
                "track_id": {"type": "string"},
                "effect": {"type": "string"},
            },
            "required": ["track_id", "effect"],
        },
    },
    {
        "name": "set_track_volume",
        "description": "Set a track's volume (0-1).",
        "input_schema": {
            "type": "object",
            "properties": {
                "track_id": {"type": "string"},
                "volume": {"type": "number"},
            },
            "required": ["track_id", "volume"],
        },
    },
    {
        "name": "repeat_clip",
        "description": (
            "Repeat an existing clip N times back-to-back after the original. "
            "This is how you build longer songs cheaply — write a 4-bar pattern "
            "once with add_clip, then repeat_clip(clip_id, times=7) fills 32 bars. "
            "Each copy gets a new auto-generated id and is placed at "
            "startBar + lengthBars * i for i in 1..times."
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
]


class NastyChatRequest(BaseModel):
    song: dict
    message: str
    history: list = []


@app.get("/nasty")
def nasty_page():
    return FileResponse(WEB_DIR / "nasty.html")


@app.post("/nasty/chat")
def nasty_chat(req: NastyChatRequest):
    user_content = (
        f"Current song state:\n```json\n{json.dumps(req.song, indent=2)}\n```\n\n"
        f"User: {req.message}"
    )
    messages = list(req.history) + [{"role": "user", "content": user_content}]
    client = _nasty_anthropic.Anthropic()

    all_tool_calls: list[dict] = []
    text_parts: list[str] = []
    stop_reason = None

    for _ in range(6):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=16000,
                system=_NASTY_SYSTEM_PROMPT,
                tools=_NASTY_TOOLS,
                messages=messages,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Claude error: {e}")

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

        # Feed synthetic tool_results back so Claude can continue chaining.
        # The actual state lives in the client; we just acknowledge and echo the
        # id Claude invented so it can reference it in follow-up calls.
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in turn_tool_uses:
            result_text = "applied"
            inp = block.input or {}
            if block.name in ("add_track", "add_clip") and "id" in inp:
                result_text = f"applied; id={inp['id']}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })
        messages.append({"role": "user", "content": tool_results})

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
