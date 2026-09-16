---
name: TAL-NoiseMaker
verified: false
last_updated: 2026-09-16
---

# TAL-NoiseMaker

Free virtual analog subtractive synthesizer from TAL-Togu Audio Line — a classic 3-oscillator VA synth with built-in Juno-style chorus, reverb, delay, and bitcrusher.

## Presets on disk

Not applicable — this plugin exposes presets via the standard VST/AU program API. Ships with 128–256 factory presets (depending on version), many by Frank "Xenox" Neumann / Particular-Sound.

## Notable parameters

- **Oscillators (Osc 1 / Osc 2 / Sub)** — saw, pulse (with PWM), triangle, noise; ±24 semitone tuning, fine tune, phase control. Sub is a square sub-oscillator.
- **Filter** — multimode with self-resonating 6dB low-pass, notch, plus additional filter types; cutoff, resonance, and adjustable filter drive.
- **Envelopes / LFOs** — ADSR (fast to very slow), plus LFOs with sine, triangle, saw, square, S&H, noise shapes; positive and negative modulation depth.
- **Ring Mod / Sync / FM** — ring modulation between oscillators, syncable triangle/saw/pulse, and FM for aggressive/metallic tones.
- **Built-in FX** — Juno-style chorus (multiple modes), reverb, delay, and a pre-filter bitcrusher affecting Osc 1 + Osc 2.
- **Voice / Portamento** — voice count and glide in the master area; a Detune control randomly detunes notes for analog drift.

## Quirks

- Mod wheel / pitch bend routings are limited to pitch, filter, and volume — no built-in mod-wheel vibrato (use MIDI learn as a workaround).
- Bitcrusher is sweepable but most of the audible action is at one end of the knob.
- Bitcrusher sits **before** the filter stage.
- No cmd/double-click parameter reset in some hosts.
- GUI has collapsible sections (Synth 1, Synth 2, Envelope Editor, Control) that can be hidden by clicking the headers.
- Some users have reported factory presets loading correctly in the VST but not the AU version — verify per host.

## Common recipes (optional)

- **Fat analog bass:** Osc1 saw + Sub square on, slight Osc2 saw detuned, LP filter ~30–50% cutoff with moderate resonance, short amp decay, a touch of filter drive.
- **Slow evolving pad:** Both oscs saw detuned, long attack/release ADSR, LP filter opening via slow LFO or envelope, add Juno chorus + reverb.
- **Classic lead:** Osc1 saw + Osc2 pulse with PWM LFO, portamento on (mono), filter ~60% with resonance, delay for space.
