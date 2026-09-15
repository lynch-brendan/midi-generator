---
name: IVGI2
verified: true
last_updated: 2026-09-15
---

# Klanghelm IVGI

Free dynamic saturation plugin from Klanghelm — a stripped-down free
version of their paid SDRR. Warm-to-gritty tube/tape/transformer-style
harmonic distortion with subtle EQ shaping baked into the saturation
curve. IVGI2 (2024 rewrite) adds a RELAXED mode and a reworked VU meter
borrowed from VUMT 2. Sits well on individual channels or across the
master bus.

## Notable parameters

- **TRIM** — pre-gain to hit ~0 dBVU on the internal meter. IVGI is
  calibrated around this level; getting trim right is step one.
- **DRIVE** — pushes the signal into the saturation stage. Reacts
  dynamically — the modeled fluctuations change with drive amount.
- **RESPONSE** — frequency dependency of the saturation. Turn left =
  lows get more saturation + high-end roll-off + low-end bump. Turn
  right (HF+) = highs get more, cleaner bass. Not a plain EQ — it's
  pre/de-emphasis filters + compression baked in.
- **ASYM MIX** — asymmetry / transparency control. Makes the negative
  half of the waveform cleaner without changing harmonic content.
  Higher values = more transparent, preserves source dynamics. 7–9 is
  the common "musical" range.
- **X-TALK** — stereo crosstalk simulation. Default around -90 dB, max
  around -60 dB. Fully counter-clockwise disables it.
- **OUTPUT** — post-gain to compensate for level changes from drive.
- **MODE** — saturation character. IVGI2 adds a RELAXED mode alongside
  the original IVGI model.

## Quirks

- No presets via standard VST3 program API — it's a knob-driven design,
  not a preset browser. Don't expect a program list.
- IVGI2 has a new plugin ID vs. IVGI v1, so both versions can coexist.
- Internal calibration is 0 dBVU — always set TRIM first, then DRIVE.
- CPU-light — safe to instantiate on every channel.

## Best uses

- Master bus glue — low drive, ASYM MIX high (7–9), RESPONSE at HF+
- Bass channel warmth and even-order harmonic thickening
- Drum bus for grit and cohesion
- Vocals when you want analog color without a compressor
- Anything that sounds "too digital" — set-and-forget subtle drive
