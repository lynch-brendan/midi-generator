import sys
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import re

sys.path.insert(0, str(Path(__file__).parent))

from core.claude_client import stream_variations
from core.midi_writer import write_midi
from core.audio_renderer import render_midi_to_wav
from core.drum_synth import render_drum_pattern
from core.variations import extract_variation_info, validate_variation, sanitize_variation

app = FastAPI()

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

WEB_DIR = Path(__file__).parent / "web"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].strip("-")


class GenerateRequest(BaseModel):
    prompt: str


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
async def generate(req: GenerateRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

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


app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
