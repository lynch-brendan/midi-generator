"""
Renders drum patterns using WAV samples.
Defaults to the Roland TR-808 pack from FL Studio for local development.
Swap SAMPLES_DIR to any folder of WAV files for production.
"""
import wave
import struct
import array
from pathlib import Path
from typing import List, Dict, Optional

SAMPLE_RATE = 44100

_BUNDLED = Path(__file__).parent.parent / "samples" / "drums"
_FL_STUDIO = Path("/Applications/FL Studio 21.app/Contents/Resources/FL/Data/Patches/Packs/All drum packs/Roland Tr-808")
SAMPLES_DIR = _BUNDLED if _BUNDLED.exists() else _FL_STUDIO

# GM pitch → sample filename in SAMPLES_DIR
GM_TO_SAMPLE = {
    36: "TR-808Kick01.wav",
    35: "TR-808Kick01.wav",
    38: "TR-808Snare01.wav",
    40: "TR-808Snare05.wav",
    37: "TR-808Rim01.wav",
    39: "TR-808Clap01.wav",
    42: "TR-808Hat_C01.wav",
    44: "TR-808Hat_C02.wav",
    46: "TR-808Hat_O01.wav",
    49: "TR-808Ride01.wav",
    51: "TR-808Ride02.wav",
    41: "TR-808Tom07.wav",
    43: "TR-808Tom06.wav",
    45: "TR-808Tom05.wav",
    47: "TR-808Tom04.wav",
    48: "TR-808Tom03.wav",
    50: "TR-808Tom01.wav",
}

_sample_cache: Dict[str, List[float]] = {}


def _load_sample(filename: str) -> Optional[List[float]]:
    if filename in _sample_cache:
        return _sample_cache[filename]

    path = SAMPLES_DIR / filename
    if not path.exists():
        return None

    try:
        with wave.open(str(path), "r") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        # Decode to floats
        if sampwidth == 2:
            samples = array.array("h", raw)
            floats = [s / 32768.0 for s in samples]
        elif sampwidth == 1:
            samples = array.array("B", raw)
            floats = [(s - 128) / 128.0 for s in samples]
        else:
            return None

        # Mix to mono if stereo
        if n_channels == 2:
            floats = [(floats[i] + floats[i + 1]) / 2 for i in range(0, len(floats) - 1, 2)]

        # Resample if needed (simple linear interpolation)
        if framerate != SAMPLE_RATE:
            ratio = framerate / SAMPLE_RATE
            new_length = int(len(floats) / ratio)
            resampled = []
            for i in range(new_length):
                pos = i * ratio
                idx = int(pos)
                frac = pos - idx
                if idx + 1 < len(floats):
                    resampled.append(floats[idx] * (1 - frac) + floats[idx + 1] * frac)
                else:
                    resampled.append(floats[idx] if idx < len(floats) else 0.0)
            floats = resampled

        _sample_cache[filename] = floats
        return floats

    except Exception as e:
        print(f"  [warn] could not load sample {filename}: {e}")
        return None


def render_drum_pattern(notes: List[Dict], tempo_bpm: int, output_path: Path) -> bool:
    """
    Render a drum pattern to WAV using real samples.
    Falls back to silence with a warning if samples aren't found.
    """
    try:
        beats_per_second = tempo_bpm / 60.0
        last_beat = max((float(n["time"]) + float(n.get("duration", 0.1))) for n in notes)
        total_samples = int((last_beat / beats_per_second + 1.0) * SAMPLE_RATE)

        buffer = [0.0] * total_samples

        for note in notes:
            pitch = int(note["pitch"])
            velocity = min(int(note.get("velocity", 100)), 127) / 127.0
            start_beat = float(note["time"])
            start_sample = int(start_beat / beats_per_second * SAMPLE_RATE)

            filename = GM_TO_SAMPLE.get(pitch)
            if not filename:
                continue

            sample_data = _load_sample(filename)
            if not sample_data:
                continue

            for i, s in enumerate(sample_data):
                idx = start_sample + i
                if idx < total_samples:
                    buffer[idx] += s * velocity

        # Normalize
        peak = max(abs(s) for s in buffer) if buffer else 1.0
        if peak > 0.9:
            buffer = [s / peak * 0.9 for s in buffer]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            for s in buffer:
                wf.writeframes(struct.pack("<h", int(max(-32767, min(32767, s * 32767)))))

        return True

    except Exception as e:
        print(f"  [warn] drum render failed: {e}")
        return False
