---
name: AUParametricEQ
verified: false
last_updated: 2026-09-16
---

# AUParametricEQ

Apple's built-in single-band parametric equalizer Audio Unit, shipped as part of macOS/iOS Core Audio.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API. No factory preset library ships on disk.

## Notable parameters
- **Center Frequency** — Global, Hz, range 20 → (SampleRate/2), default 2000 Hz.
- **Q** — Global, Hz units in the header, range 0.1 → 20, default 1.0. Controls bandwidth/resonance of the band.
- **Gain** — Global, dB, range -20 → +20, default 0 dB.

## Quirks
- Single-band only. To sculpt a full frequency response you must instantiate multiple copies in series (users routinely chain 3–4 instances to shape headphone/instrument tone).
- No custom UI in most hosts — typically shows Apple's generic Cocoa parameter view (sliders only, no graphical EQ curve).
- Default center frequency is 2 kHz with 0 dB gain, so a freshly instantiated unit is audibly transparent until Gain is moved.
- Center Frequency upper bound is tied to the current sample rate (Nyquist), not a fixed value like 20 kHz.
- Filter type is fixed (parametric peaking); no shelf, high-pass, or low-pass modes.
