"""
Karplus-Strong plucked string synthesis for guitar GM patches (24-31).
Pure Python ring-buffer implementation — no external audio dependencies.
"""
import wave
import struct
import random
import math
from pathlib import Path
from typing import List, Dict

SAMPLE_RATE = 44100

# GM patch → (decay, brightness, dur_scale)
# decay:      per-sample attenuation (closer to 1.0 = longer sustain)
# brightness: low-pass blend weight for current vs. next sample (higher = brighter)
# dur_scale:  multiply note duration before computing KS tail length
_PATCH_PARAMS = {
    24: (0.9996, 0.48, 1.2),   # Nylon acoustic — warm, long sustain
    25: (0.9995, 0.52, 1.1),   # Steel acoustic — brighter
    26: (0.9993, 0.50, 1.0),   # Jazz electric — moderate
    27: (0.9994, 0.51, 1.0),   # Clean electric — moderate
    28: (0.9970, 0.50, 0.35),  # Muted — very short
    29: (0.9992, 0.53, 1.0),   # Overdrive
    30: (0.9990, 0.54, 0.9),   # Distortion — brighter, slightly shorter
    31: (0.9997, 0.46, 1.5),   # Harmonics — warmest, longest
}
_DEFAULT_PARAMS = (0.9993, 0.50, 1.0)


def _midi_to_hz(pitch: int) -> float:
    return 440.0 * (2.0 ** ((pitch - 69) / 12.0))


def _ks_tone(freq: float, duration_sec: float, velocity: float,
              decay: float, brightness: float, seed: int = 0) -> List[float]:
    """Karplus-Strong ring-buffer synthesis — O(1) per sample."""
    buf_len = max(2, int(SAMPLE_RATE / freq))
    total_samples = int(duration_sec * SAMPLE_RATE)

    rng = random.Random(seed)
    buf = [rng.uniform(-1.0, 1.0) * velocity for _ in range(buf_len)]

    output = [0.0] * total_samples
    pos = 0
    for i in range(total_samples):
        output[i] = buf[pos]
        nxt = (pos + 1) % buf_len
        # Low-pass filter + per-sample decay
        buf[pos] = decay * (brightness * buf[pos] + (1.0 - brightness) * buf[nxt])
        pos = nxt

    return output


def _soft_clip(x: float) -> float:
    """Gentle tanh waveshaper for overdrive/distortion patches."""
    return math.tanh(x * 1.8) / math.tanh(1.8)


def render_guitar_pattern(
    notes: List[Dict],
    tempo_bpm: int,
    gm_patch: int,
    output_path: Path,
    bars: int = 4,
) -> bool:
    """
    Render a guitar MIDI note list to WAV using Karplus-Strong synthesis.
    Output is padded to exactly bars × 4 beats so it snaps to DAW grids.
    Returns True on success.
    """
    try:
        decay, brightness, dur_scale = _PATCH_PARAMS.get(gm_patch, _DEFAULT_PARAMS)
        use_clip = gm_patch in (29, 30)  # overdrive / distortion

        beats_per_second = tempo_bpm / 60.0
        total_samples = int((bars * 4.0 / beats_per_second) * SAMPLE_RATE)
        buf = [0.0] * total_samples

        for idx, note in enumerate(notes):
            pitch = int(note["pitch"])
            velocity = min(int(note.get("velocity", 100)), 127) / 127.0
            start_beat = float(note["time"])
            note_dur_beats = float(note.get("duration", 0.5)) * dur_scale

            freq = _midi_to_hz(pitch)
            # KS tail: note duration + natural decay room (0.8 s gives the string space to ring)
            tone_sec = note_dur_beats / beats_per_second + 0.8
            tone = _ks_tone(freq, tone_sec, velocity, decay, brightness, seed=idx)

            if use_clip:
                tone = [_soft_clip(s) for s in tone]

            start_sample = int(start_beat / beats_per_second * SAMPLE_RATE)
            for i, s in enumerate(tone):
                dest = start_sample + i
                if dest < total_samples:
                    buf[dest] += s

        # Normalize
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
        print(f"  [warn] guitar render failed: {e}")
        return False
