---
name: Odin2
verified: false
last_updated: 2026-09-16
---

# Odin2

Free open-source 24-voice semi-modular hybrid synthesizer with three flexible oscillator slots, three analog-modeled filter slots, and a large modulation matrix.

## Presets on disk

Odin2 uses `.odin` files for its native preset format. Location varies by platform and is user-configurable; omitting an exact path here since it isn't verified.

## Notable parameters

- **Oscillator Slots (x3)**: each can host Analog, Wavetable, Multi, Vector, Chiptune, FM, PhaseMod, Noise, or user-drawn wave/spectrum/chiptune.
- **Filter Slots (x3)**: two pre-amp, one post-amp — Ladder (Moog-style), KRG-35 (Korg-35), SEM (Oberheim), plus others; oscillators can be routed to filters 1/2 selectively.
- **Envelopes**: four ADSRs (separate envelopes available for oscillators and filters).
- **LFOs**: four LFOs (three per-voice + one global).
- **Modulation Matrix**: large mod matrix (~18 slots) for routing any source to any destination.
- **FX Section**: Delay, Phaser, Flanger, Chorus, Distortion, Reverb.
- **XY-Pad**, **Arpeggiator**, and **Microtuning** (.kbm / .scl support).

## Quirks

- Semi-modular routing: which oscillators feed which filters must be explicitly selected — a fresh patch may be silent until routing is correct.
- Native preset extension is `.odin`; some third-party banks may use `.osb` or a different extension and require manual import.
- Reported polyphony ceiling is 24 voices, but older beta versions and some user reports mention lower effective polyphony (~12) — treat max voices as approximate.
- Randomizing all parameters (e.g. via FL Studio's randomize) often yields silence because of routing dependencies; targeted randomization works better.
- Default init patch is minimal — not representative of the synth's character.

## Common recipes

- **Warm analog bass**: Osc1 Analog saw + slight detune → Ladder filter (low cutoff, moderate resonance) → short amp env, tight filter env with negative-ish decay.
- **Wavetable lead**: Osc1 Wavetable + Osc2 Analog square (octave up) → SEM filter (band-pass or high-pass) → chorus + delay, LFO to wavetable position.
- **Evolving pad**: Osc1 Vector + Osc2 Wavetable, detuned unison → Ladder LP (moderate cutoff) → slow LFO to XY-Pad / wavetable pos → reverb + chorus, long ADSR.
- **Chiptune lead**: Osc1 Chiptune, minimal filter, arpeggiator on.
