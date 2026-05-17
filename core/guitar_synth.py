"""
Sample-based guitar renderer using the quartertone ClassicalGuitar-multisampled pack.
Samples live in samples/guitar_classical/ — individual note WAVs, 5 velocity layers,
MIDI range 35-82. Pitch-shifts via linear-interpolation resampling to cover all pitches.
"""
import wave
import struct
import array
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SAMPLE_RATE = 44100
SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "guitar_classical"

# midi_note -> {vel_layer(1-5) -> Path}
_index: Optional[Dict[int, Dict[int, Path]]] = None
_sample_cache: Dict[str, List[float]] = {}

_SAMPLE_RE = re.compile(r"gtrclass-(?:n?\d+)f\ds(\d+)v(\d+)", re.IGNORECASE)


def _build_index() -> Dict[int, Dict[int, Path]]:
    index: Dict[int, Dict[int, Path]] = {}
    if not SAMPLES_DIR.exists():
        return index
    for path in SAMPLES_DIR.glob("*.wav"):
        m = _SAMPLE_RE.search(path.stem)
        if not m:
            continue
        midi = int(m.group(1))
        vel = int(m.group(2))
        if midi not in index:
            index[midi] = {}
        index[midi][vel] = path
    return index


def _get_index() -> Dict[int, Dict[int, Path]]:
    global _index
    if _index is None:
        _index = _build_index()
    return _index


def _load_sample(path: Path) -> Optional[List[float]]:
    key = str(path)
    if key in _sample_cache:
        return _sample_cache[key]
    try:
        with wave.open(str(path), "r") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sampwidth == 2:
            ints = array.array("h", raw)
            floats = [s / 32768.0 for s in ints]
        elif sampwidth == 3:
            floats = []
            for i in range(0, len(raw) - 2, 3):
                val = int.from_bytes(raw[i:i + 3], "little", signed=True)
                floats.append(val / 8388608.0)
        else:
            return None

        if n_channels == 2:
            floats = [(floats[i] + floats[i + 1]) / 2.0 for i in range(0, len(floats) - 1, 2)]

        # Resample from source rate to our output rate
        if framerate != SAMPLE_RATE:
            ratio = framerate / SAMPLE_RATE
            new_len = int(len(floats) / ratio)
            resampled = []
            for i in range(new_len):
                pos = i * ratio
                idx = int(pos)
                frac = pos - idx
                if idx + 1 < len(floats):
                    resampled.append(floats[idx] * (1 - frac) + floats[idx + 1] * frac)
                elif idx < len(floats):
                    resampled.append(floats[idx])
            floats = resampled

        _sample_cache[key] = floats
        return floats
    except Exception as e:
        print(f"  [guitar_synth] could not load {path.name}: {e}")
        return None


def _pitch_shift(samples: List[float], semitones: float) -> List[float]:
    if abs(semitones) < 0.01:
        return list(samples)
    ratio = 2.0 ** (semitones / 12.0)
    new_len = int(len(samples) / ratio)
    if new_len <= 0:
        return []
    out = []
    for i in range(new_len):
        pos = i * ratio
        idx = int(pos)
        frac = pos - idx
        if idx + 1 < len(samples):
            out.append(samples[idx] * (1 - frac) + samples[idx + 1] * frac)
        elif idx < len(samples):
            out.append(samples[idx])
        else:
            break
    return out


def _pick_sample(target_midi: int, velocity: int) -> Optional[Tuple[Path, int]]:
    index = _get_index()
    if not index:
        return None
    nearest = min(index.keys(), key=lambda n: abs(n - target_midi))
    vel_layer = min(5, max(1, math.ceil(velocity / 127.0 * 5)))
    layers = index[nearest]
    best_layer = min(layers.keys(), key=lambda v: abs(v - vel_layer))
    return layers[best_layer], nearest


def is_available() -> bool:
    return bool(_get_index())


def render_guitar_pattern(
    notes: List[Dict],
    tempo_bpm: int,
    gm_patch: int,
    output_path: Path,
    bars: int = 4,
) -> bool:
    """
    Render a guitar note list to WAV using real samples + pitch shifting.
    Returns True on success, False if samples aren't available (caller falls back to FluidSynth).
    """
    if not is_available():
        print("  [guitar_synth] sample directory not found, falling back")
        return False

    try:
        beats_per_second = tempo_bpm / 60.0
        total_samples = int((bars * 4.0 / beats_per_second) * SAMPLE_RATE)
        buf = [0.0] * total_samples

        for note in notes:
            pitch = int(note["pitch"])
            velocity = min(int(note.get("velocity", 100)), 127)
            start_beat = float(note["time"])
            note_dur_beats = float(note.get("duration", 0.5))

            result = _pick_sample(pitch, velocity)
            if result is None:
                continue
            sample_path, sample_midi = result

            raw = _load_sample(sample_path)
            if raw is None:
                continue

            shifted = _pitch_shift(raw, pitch - sample_midi)

            # Allow note duration + 2.5 s of natural decay, then silence
            max_samples = int((note_dur_beats / beats_per_second + 2.5) * SAMPLE_RATE)
            shifted = shifted[:max_samples]

            vel_scale = velocity / 127.0
            start_sample = int(start_beat / beats_per_second * SAMPLE_RATE)
            for i, s in enumerate(shifted):
                dest = start_sample + i
                if dest < total_samples:
                    buf[dest] += s * vel_scale

        peak = max(abs(s) for s in buf) if buf else 0.0
        if peak > 0.9:
            scale = 0.9 / peak
            buf = [s * scale for s in buf]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            for s in buf:
                v = int(max(-32767, min(32767, s * 32767)))
                wf.writeframes(struct.pack("<hh", v, v))

        return True

    except Exception as e:
        print(f"  [guitar_synth] render failed: {e}")
        return False
