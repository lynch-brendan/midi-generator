---
name: AUNewPitch
verified: false
last_updated: 2026-09-16
---

# AUNewPitch

Apple's built-in Audio Unit pitch-shifter effect, available in Logic Pro and GarageBand on macOS/iOS, offering precise fine-tuned pitch scaling of audio.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API (managed by the host DAW).

## Notable parameters
- **Pitch Scale** — the primary control, a fine-resolution slider measured in cents (thousands) that sets the pitch-shift amount. It can be automated, e.g. raised by 200 cents to shift a whole step.
- **Overlap** — exposed under the Parameters disclosure, adjusts grain overlap for the shifting algorithm.
- **Peak Locking** — checkbox under Parameters to reduce phasiness on tonal material.
- **Render Quality** — algorithm quality selector with Minimum / Low / Medium / High / Maximum options (trade CPU for artifacts).

## Quirks
- Extremely minimal UI compared to Logic's Pitch Shifter — essentially a single big slider plus an expandable Parameters section, so users looking for semitone knobs won't find them (everything is in cents).
- Lives in the "Apple" AU category in Logic Pro (Audio FX → Apple → AUNewPitch), not in the "Pitch" category by default; it can be moved via the Plug-in Manager.
- Works on both audio and MIDI (instrument) tracks in Logic as an insert effect.
- Not intended as a formant-preserving vocal tuner — for large shifts on vocals, Logic's Pitch Shifter or Pitch Correction/Flex Pitch usually sound better. AUNewPitch shines for subtle detune and precise cent-level correction.
- macOS/iOS-only (Audio Unit format); no VST/AAX version exists.
