import sys
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from collections import defaultdict
from datetime import date
import os
import re
from typing import Optional

# {ip: {date: count}}
_rate_counts: dict = defaultdict(lambda: defaultdict(int))
DAILY_LIMIT = 5

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
async def generate(req: GenerateRequest, request: Request):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    admin_ips = {x.strip() for x in os.environ.get("ADMIN_IPS", "").split(",") if x.strip()}
    if ip not in admin_ips:
        today = date.today()
        if _rate_counts[ip][today] >= DAILY_LIMIT:
            raise HTTPException(status_code=429, detail=f"Limit of {DAILY_LIMIT} generations per day reached. Come back tomorrow!")
        _rate_counts[ip][today] += 1

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
