#!/usr/bin/env python3
"""
Synthesize royalty-free 808-style drum samples using pure Python.
No external dependencies — only the standard library.
Run this to replace any previously bundled samples with legally clean WAV files.
"""
import wave
import struct
import math
import random
from pathlib import Path

SAMPLE_RATE = 44100
OUTPUT_DIR = Path(__file__).parent.parent / "samples" / "drums"


def write_wav(path: Path, samples: list):
    peak = max(abs(s) for s in samples) if samples else 1.0
    if peak > 0:
        samples = [s / peak * 0.9 for s in samples]
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        for s in samples:
            wf.writeframes(struct.pack("<h", int(max(-32767, min(32767, s * 32767)))))


def exp_decay(t: float, tau: float) -> float:
    return math.exp(-t / tau) if tau > 0 else (1.0 if t == 0 else 0.0)


def sine(freq: float, t: float) -> float:
    return math.sin(2 * math.pi * freq * t)


def noise() -> float:
    return random.uniform(-1, 1)


def kick(duration=0.8, start_freq=185, end_freq=48, pitch_tau=0.055, amp_tau=0.24, click=0.25):
    """808 kick: exponential pitch sweep + click transient."""
    n = int(SAMPLE_RATE * duration)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = end_freq + (start_freq - end_freq) * math.exp(-t / pitch_tau)
        amp = exp_decay(t, amp_tau)
        transient = click * exp_decay(t, 0.003) * noise()
        phase += 2 * math.pi * freq / SAMPLE_RATE
        out.append(amp * math.sin(phase) + transient)
    return out


def snare(duration=0.28, tone_freq=200, tone_tau=0.045, noise_tau=0.14, tone_mix=0.38):
    """808 snare: sine body + white noise tail + click."""
    n = int(SAMPLE_RATE * duration)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        body = tone_mix * exp_decay(t, tone_tau) * sine(tone_freq, t)
        hiss = (1 - tone_mix) * exp_decay(t, noise_tau) * noise()
        click_ = 0.25 * exp_decay(t, 0.003) * noise()
        out.append(body + hiss + click_)
    return out


def hihat_closed(duration=0.08):
    n = int(SAMPLE_RATE * duration)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        out.append(exp_decay(t, 0.014) * noise())
    return out


def hihat_open(duration=0.38):
    n = int(SAMPLE_RATE * duration)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        out.append(exp_decay(t, 0.11) * noise())
    return out


def clap(duration=0.18):
    """Three staggered noise bursts — the classic clap smear."""
    n = int(SAMPLE_RATE * duration)
    out = [0.0] * n
    for offset_ms in [0, 8, 17]:
        offset = int(offset_ms * SAMPLE_RATE / 1000)
        for i in range(n - offset):
            t = i / SAMPLE_RATE
            out[offset + i] += exp_decay(t, 0.022) * noise() * 0.45
    return out


def rim(duration=0.09, freq=420):
    n = int(SAMPLE_RATE * duration)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        amp = exp_decay(t, 0.016)
        out.append(amp * (0.5 * sine(freq, t) + 0.5 * noise()))
    return out


def tom(duration=0.42, start_freq=130, end_freq=55, amp_tau=0.15):
    n = int(SAMPLE_RATE * duration)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = end_freq + (start_freq - end_freq) * math.exp(-t / 0.038)
        amp = exp_decay(t, amp_tau)
        phase += 2 * math.pi * freq / SAMPLE_RATE
        out.append(amp * math.sin(phase))
    return out


def crash(duration=1.0):
    """Crash: long noisy decay with metallic overtones."""
    n = int(SAMPLE_RATE * duration)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        amp = exp_decay(t, 0.32)
        shimmer = 0.2 * (sine(3200, t) + sine(4750, t) + sine(6100, t))
        out.append(amp * (0.72 * noise() + 0.28 * shimmer))
    return out


def ride(duration=0.55):
    """Ride: sustained bell + noise."""
    n = int(SAMPLE_RATE * duration)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        amp = exp_decay(t, 0.22)
        bell = (sine(980, t) + 0.5 * sine(2750, t) + 0.3 * sine(4150, t)) / 1.8
        out.append(amp * (0.5 * bell + 0.5 * noise()))
    return out


SAMPLES = {
    "TR-808Kick01.wav":  kick(0.80, 185, 48, 0.055, 0.24),
    "TR-808Snare01.wav": snare(0.28, 200, 0.045, 0.14, 0.38),
    "TR-808Snare05.wav": snare(0.20, 240, 0.030, 0.10, 0.30),
    "TR-808Rim01.wav":   rim(0.09, 420),
    "TR-808Clap01.wav":  clap(0.18),
    "TR-808Hat_C01.wav": hihat_closed(0.08),
    "TR-808Hat_C02.wav": hihat_closed(0.06),
    "TR-808Hat_O01.wav": hihat_open(0.38),
    "TR-808Ride01.wav":  crash(1.0),
    "TR-808Ride02.wav":  ride(0.55),
    "TR-808Tom01.wav":   tom(0.32, 200, 82, 0.12),
    "TR-808Tom03.wav":   tom(0.38, 165, 67, 0.14),
    "TR-808Tom04.wav":   tom(0.40, 142, 58, 0.15),
    "TR-808Tom05.wav":   tom(0.44, 122, 50, 0.16),
    "TR-808Tom06.wav":   tom(0.50, 100, 44, 0.18),
    "TR-808Tom07.wav":   tom(0.56,  82, 38, 0.20),
}

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, data in SAMPLES.items():
        write_wav(OUTPUT_DIR / filename, data)
        print(f"  ✓ {filename}  ({len(data) / SAMPLE_RATE:.2f}s)")
    print(f"\n{len(SAMPLES)} royalty-free samples written to {OUTPUT_DIR}")
