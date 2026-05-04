"""
Render MIDI files to WAV using FluidSynth + a SF2 soundfont.
FluidSynth must be installed on the system (brew install fluidsynth / apt install fluidsynth).
"""
import os
import shutil
import subprocess
from pathlib import Path


SOUNDFONT_PATHS = [
    # Written by setup.sh
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

        return wav_path.exists()

    except RuntimeError as e:
        print(f"  [warn] {e}")
        return False
    except subprocess.TimeoutExpired:
        print(f"  [warn] fluidsynth timed out rendering {midi_path.name}")
        return False
    except Exception as e:
        print(f"  [warn] Audio render failed for {midi_path.name}: {e}")
        return False
