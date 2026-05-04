#!/usr/bin/env python3
"""
MIDI & Audio Generator
Usage: python3 generate.py "jazzy piano riff in D minor"
"""
import re
import sys
from pathlib import Path

# Ensure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from core.claude_client import generate_variations
from core.midi_writer import write_midi
from core.audio_renderer import render_midi_to_wav
from core.variations import extract_variation_info, validate_variation, sanitize_variation


def slugify(text: str) -> str:
    """Convert a prompt string to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].strip("-")


def print_header(prompt: str) -> None:
    bar = "─" * 56
    print(f"\n{bar}")
    print(f"  Generating 5 variations for: \"{prompt}\"")
    print(f"{bar}")


def print_variation_summary(info, midi_ok: bool, wav_ok: bool) -> None:
    midi_status = "MIDI" if midi_ok else "MIDI(err)"
    wav_status = "WAV" if wav_ok else "WAV(skipped)"
    print(
        f"  [{info.id}] {info.name:<28}  {info.tempo} BPM  "
        f"{info.note_count:>2} notes  [{midi_status} + {wav_status}]"
    )
    print(f"       {info.character}")


def run(prompt: str) -> None:
    print_header(prompt)

    # ── Generate via Claude ────────────────────────────────────────────────
    print("\n  Calling Claude API...")
    try:
        data = generate_variations(prompt)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    instrument = data.get("instrument", "unknown")
    gm_patch = int(data.get("gm_patch", 0))
    key = data.get("key", "unknown key")
    variations = data.get("variations", [])

    print(f"  Instrument: {instrument}  |  Key: {key}  |  GM patch: {gm_patch}")
    print(f"  Got {len(variations)} variation(s) — writing files...\n")

    # ── Set up output directory ────────────────────────────────────────────
    slug = slugify(prompt)
    out_dir = Path("output") / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Write MIDI + render audio ──────────────────────────────────────────
    results = []
    for var in variations:
        var = sanitize_variation(var)

        warnings = validate_variation(var)
        if warnings:
            print(f"  [warn] variation {var.get('id')}: {'; '.join(warnings)}")

        info = extract_variation_info(var)
        idx = str(info.id).zfill(2)
        var_slug = slugify(info.name)
        midi_path = out_dir / f"{idx}-{var_slug}.mid"
        wav_path = out_dir / f"{idx}-{var_slug}.wav"

        # Write MIDI
        midi_ok = False
        try:
            write_midi(midi_path, var["notes"], info.tempo, gm_patch)
            midi_ok = True
        except Exception as e:
            print(f"  [error] MIDI write failed for variation {info.id}: {e}")

        # Render audio
        wav_ok = False
        if midi_ok:
            wav_ok = render_midi_to_wav(midi_path, wav_path)

        print_variation_summary(info, midi_ok, wav_ok)
        results.append((info, midi_ok, wav_ok))

    # ── Summary ───────────────────────────────────────────────────────────
    midi_count = sum(1 for _, m, _ in results if m)
    wav_count = sum(1 for _, _, w in results if w)
    print(f"\n  Output: {out_dir}/")
    print(f"  {midi_count} MIDI file(s)  •  {wav_count} WAV file(s)")

    if wav_count == 0:
        print(
            "\n  TIP: No audio rendered. Run setup.sh to install FluidSynth + soundfont."
        )

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate.py \"<your musical idea>\"")
        print('  e.g. python3 generate.py "jazzy piano riff in D minor"')
        sys.exit(1)

    user_prompt = " ".join(sys.argv[1:])
    run(user_prompt)
