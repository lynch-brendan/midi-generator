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


def trim_trailing_silence(wav_path: Path, threshold: float = 0.005, padding: float = 0.3) -> None:
    """Trim trailing silence from a WAV file in-place.

    threshold: amplitude fraction (0–1) below which samples are considered silent
    padding:   seconds of audio to keep after the last loud sample
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
            max_val = 32768
        elif sampwidth == 4:
            samples = array.array("i", raw)
            max_val = 2147483648
        else:
            return  # unsupported width, leave file alone

        # Scan backwards for last sample above threshold
        last_active = 0
        for i in range(len(samples) - 1, -1, -1):
            if abs(samples[i]) / max_val > threshold:
                last_active = i
                break

        padding_samples = int(framerate * padding) * n_channels
        end = min(last_active + padding_samples, len(samples))
        end -= end % n_channels  # align to frame boundary

        if end >= len(samples):
            return  # nothing to trim

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(n_channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(framerate)
            wf.writeframes(samples[:end].tobytes())

    except Exception as e:
        print(f"  [warn] silence trim failed for {wav_path.name}: {e}")


def render_midi_to_wav(midi_path: Path, wav_path: Path) -> bool:
    """
    Render a MIDI file to WAV. Returns True on success, False on failure.
    Prints a warning but does not raise — MIDI files are still saved even if audio fails.
    """
    try:
        fluidsynth = _find_fluidsynth()
        soundfont = _find_soundfont()

        result = subprocess.run(
            [
                fluidsynth,
                "-ni",                   # no interactive mode
                "-q",                    # quiet
                "-F", str(wav_path),     # output file
                "-r", "44100",           # sample rate
                str(soundfont),
                str(midi_path),
            ],
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"  [warn] fluidsynth error for {midi_path.name}: {result.stderr.decode().strip()}")
            return False

        if wav_path.exists():
            trim_trailing_silence(wav_path)
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
