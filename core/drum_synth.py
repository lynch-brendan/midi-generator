"""
Renders drum patterns using WAV samples.
Defaults to the Roland TR-808 pack from FL Studio for local development.
Swap SAMPLES_DIR to any folder of WAV files for production.

Pass kit_name to render_drum_pattern() to use a kit fetched from R2 via drum_kits.
"""
import wave
import struct
import array
from pathlib import Path
from typing import List, Dict, Optional

from core import drum_kits

SAMPLE_RATE = 44100

_BUNDLED = Path(__file__).parent.parent / "samples" / "drums"
_FL_STUDIO = Path("/Applications/FL Studio 21.app/Contents/Resources/FL/Data/Patches/Packs/All drum packs/Roland Tr-808")
SAMPLES_DIR = _BUNDLED if _BUNDLED.exists() else _FL_STUDIO

# GM pitch → stereo pan (-1.0 full left, 0.0 center, 1.0 full right)
# Mimics a standard drum kit viewed from the drummer's perspective
GM_DRUM_PAN = {
    36: 0.0,    # kick — center
    35: 0.0,    # kick variant — center
    38: 0.05,   # snare — slightly right
    40: 0.05,   # snare variant
    37: -0.1,   # rim — slightly left
    39: -0.1,   # clap — slightly left
    42: -0.4,   # closed hi-hat — left
    44: -0.4,   # pedal hi-hat — left
    46: 0.4,    # open hi-hat — right
    49: 0.5,    # crash — far right
    51: 0.45,   # ride — right
    41: -0.35,  # low tom — left
    43: -0.2,   # low-mid tom
    45: -0.05,  # mid tom — near center
    47: 0.15,   # mid-high tom
    48: 0.25,   # high-mid tom
    50: 0.4,    # high tom — right
}

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


def _add_early_reflections(buf: List[float]) -> List[float]:
    # Short delay taps simulate a small live room without washing out the transients
    taps = [(7, 0.15), (14, 0.10), (23, 0.06)]
    out = list(buf)
    for delay_ms, gain in taps:
        delay_samples = int(delay_ms * SAMPLE_RATE / 1000)
        for i in range(delay_samples, len(out)):
            out[i] += buf[i - delay_samples] * gain
    return out


def _load_sample(filename: str, samples_dir: Path = None) -> Optional[List[float]]:
    if samples_dir is None:
        samples_dir = SAMPLES_DIR

    cache_key = str(samples_dir / filename)
    if cache_key in _sample_cache:
        return _sample_cache[cache_key]

    path = samples_dir / filename
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

        _sample_cache[cache_key] = floats
        return floats

    except Exception as e:
        print(f"  [warn] could not load sample {filename}: {e}")
        return None


def render_drum_pattern(
    notes: List[Dict],
    tempo_bpm: int,
    output_path: Path,
    kit_name: Optional[str] = None,
) -> bool:
    """
    Render a drum pattern to WAV using real samples.

    If kit_name is provided, drum_kits.get_kit_dir() is used to locate samples
    and drum_kits.auto_map_kit() builds the GM→filename mapping dynamically.
    Falls back to the bundled/FL Studio Roland TR-808 samples when kit_name is
    None or the kit cannot be fetched.

    Falls back to silence with a warning if no samples are found at all.
    """
    # Resolve samples directory and pitch→filename mapping
    active_samples_dir: Path = SAMPLES_DIR
    active_gm_map: Dict[int, str] = GM_TO_SAMPLE

    if kit_name:
        kit_dir = drum_kits.get_kit_dir(kit_name)
        if kit_dir is not None:
            mapped = drum_kits.auto_map_kit(kit_dir)
            if mapped:
                active_samples_dir = kit_dir
                active_gm_map = mapped
            else:
                print(f"  [drum_synth] auto_map_kit returned empty for '{kit_name}', using fallback")
        else:
            print(f"  [drum_synth] kit '{kit_name}' unavailable, using fallback")

    try:
        beats_per_second = tempo_bpm / 60.0
        last_beat = max((float(n["time"]) + float(n.get("duration", 0.1))) for n in notes)
        total_samples = int((last_beat / beats_per_second + 1.0) * SAMPLE_RATE)

        buf_l = [0.0] * total_samples
        buf_r = [0.0] * total_samples

        for note in notes:
            pitch = int(note["pitch"])
            velocity = min(int(note.get("velocity", 100)), 127) / 127.0
            start_beat = float(note["time"])
            start_sample = int(start_beat / beats_per_second * SAMPLE_RATE)

            filename = active_gm_map.get(pitch)
            if not filename:
                continue

            sample_data = _load_sample(filename, active_samples_dir)
            if not sample_data:
                continue

            pan = GM_DRUM_PAN.get(pitch, 0.0)
            gain_l = (1.0 - pan) / 2.0
            gain_r = (1.0 + pan) / 2.0

            for i, s in enumerate(sample_data):
                idx = start_sample + i
                if idx < total_samples:
                    v = s * velocity
                    buf_l[idx] += v * gain_l
                    buf_r[idx] += v * gain_r

        # Add a light room feel via early reflections
        buf_l = _add_early_reflections(buf_l)
        buf_r = _add_early_reflections(buf_r)

        # Normalize both channels together so the stereo image is preserved
        peak = max((max(abs(s) for s in buf_l) if buf_l else 0.0),
                   (max(abs(s) for s in buf_r) if buf_r else 0.0))
        if peak > 0.9:
            scale = 0.9 / peak
            buf_l = [s * scale for s in buf_l]
            buf_r = [s * scale for s in buf_r]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            for l, r in zip(buf_l, buf_r):
                wf.writeframes(struct.pack("<hh",
                    int(max(-32767, min(32767, l * 32767))),
                    int(max(-32767, min(32767, r * 32767))),
                ))

        return True

    except Exception as e:
        print(f"  [warn] drum render failed: {e}")
        return False
