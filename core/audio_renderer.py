"""
Render MIDI files to WAV using FluidSynth + a SF2 soundfont.
FluidSynth must be installed on the system (brew install fluidsynth / apt install fluidsynth).
"""
import array
import os
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Optional


# Reverb presets keyed by instrument family
_REVERB_PRESETS = {
    # Bass — keep dry so low-end doesn't get muddy
    "none": {"synth.reverb.active": "0"},
    # Piano, guitar, brass, leads — small room presence
    "room": {
        "synth.reverb.active": "1",
        "synth.reverb.room-size": "0.25",
        "synth.reverb.damping": "0.5",
        "synth.reverb.level": "0.35",
        "synth.reverb.width": "0.5",
    },
    # Strings, pads, ensemble, pipe — wide hall
    "hall": {
        "synth.reverb.active": "1",
        "synth.reverb.room-size": "0.65",
        "synth.reverb.damping": "0.3",
        "synth.reverb.level": "0.45",
        "synth.reverb.width": "0.9",
    },
}


def _reverb_preset_for_patch(gm_patch: Optional[int]) -> str:
    if gm_patch is None:
        return "room"
    if 32 <= gm_patch <= 39:
        return "none"
    if (40 <= gm_patch <= 55) or (72 <= gm_patch <= 79) or (88 <= gm_patch <= 103):
        return "hall"
    return "room"


SOUNDFONT_PATHS = [
    # Primary — downloaded by Dockerfile / setup.sh
    Path(__file__).parent.parent / "soundfonts" / "MuseScore_General.sf2",
    # Legacy fallback
    Path(__file__).parent.parent / "soundfonts" / "GeneralUser.sf2",
    # Common system locations
    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
    Path("/usr/share/soundfonts/FluidR3_GM.sf2"),
    Path("/usr/local/share/sounds/sf2/GeneralUser.sf2"),
    Path(os.path.expanduser("~/soundfonts/GeneralUser.sf2")),
]


def _find_fluidsynth() -> str:
    path = shutil.which("fluidsynth")
    if path:
        return path
    for candidate in ["/opt/homebrew/bin/fluidsynth", "/usr/local/bin/fluidsynth"]:
        if os.path.exists(candidate):
            return candidate
    raise RuntimeError(
        "fluidsynth not found. Run setup.sh or install manually:\n"
        "  macOS:  brew install fluidsynth\n"
        "  Ubuntu: sudo apt install fluidsynth"
    )


def _find_soundfont() -> Path:
    for sf_path in SOUNDFONT_PATHS:
        if sf_path.exists():
            return sf_path
    raise RuntimeError(
        "No SF2 soundfont found. Run setup.sh to download one, or set a path manually.\n"
        "Checked locations:\n" + "\n".join(f"  {p}" for p in SOUNDFONT_PATHS)
    )


def pad_to_bar_duration(wav_path: Path, target_seconds: float) -> None:
    """Pad (or trim) a WAV file in-place to exactly target_seconds.

    This ensures rendered clips snap perfectly to DAW grids when looped.
    """
    try:
        with wave.open(str(wav_path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sampwidth == 2:
            samples = array.array("h", raw)
        elif sampwidth == 4:
            samples = array.array("i", raw)
        else:
            return

        target_samples = int(target_seconds * framerate) * n_channels
        target_samples -= target_samples % n_channels  # align to frame boundary

        if len(samples) < target_samples:
            samples.extend([0] * (target_samples - len(samples)))
        elif len(samples) > target_samples:
            samples = samples[:target_samples]
        else:
            return  # already exact

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(n_channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(framerate)
            wf.writeframes(samples.tobytes())

    except Exception as e:
        print(f"  [warn] pad_to_bar_duration failed for {wav_path.name}: {e}")


def render_midi_to_wav(
    midi_path: Path,
    wav_path: Path,
    gm_patch: Optional[int] = None,
    tempo: Optional[float] = None,
    bars: Optional[int] = None,
) -> bool:
    """
    Render a MIDI file to WAV. Returns True on success, False on failure.
    Prints a warning but does not raise — MIDI files are still saved even if audio fails.
    When tempo and bars are provided, the WAV is padded to exactly bars*4 beats long.
    """
    try:
        fluidsynth = _find_fluidsynth()
        soundfont = _find_soundfont()

        preset = _REVERB_PRESETS[_reverb_preset_for_patch(gm_patch)]
        reverb_flags = []
        for key, val in preset.items():
            reverb_flags += ["-o", f"{key}={val}"]

        base_flags = ["-ni", "-o", "audio.driver=file", "-F", str(wav_path), "-r", "22050"]

        def _run(extra):
            cmd = [fluidsynth] + base_flags + extra + [str(soundfont), str(midi_path)]
            print(f"  [fluidsynth] {' '.join(cmd)}")
            return subprocess.run(cmd, capture_output=True, timeout=30)

        result = _run(reverb_flags)
        if result.returncode != 0:
            print(f"  [fluidsynth] reverb attempt failed (rc={result.returncode}): {result.stderr.decode().strip()}")
            if wav_path.exists():
                wav_path.unlink()
            result = _run([])
        if result.returncode != 0:
            print(f"  [fluidsynth] plain attempt failed (rc={result.returncode}): {result.stderr.decode().strip()}")
            return False

        if wav_path.exists():
            if tempo and bars:
                target_seconds = bars * 4 * (60.0 / tempo)
                pad_to_bar_duration(wav_path, target_seconds)
            return True
        return False

    except RuntimeError as e:
        print(f"  [warn] {e}")
        return False
    except subprocess.TimeoutExpired:
        print(f"  [warn] fluidsynth timed out rendering {midi_path.name}")
        return False
    except Exception as e:
        print(f"  [warn] Audio render failed for {midi_path.name}: {e}")
        return False
