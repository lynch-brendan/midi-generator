---
name: AUMultibandCompressor
verified: false
last_updated: 2026-09-16
---

# AUMultibandCompressor

Apple's built-in four-band compressor Audio Unit, bundled with macOS and used by GarageBand/Logic and other AU hosts.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API. Any user presets saved from a host are typically stored as `.aupreset` files under `~/Library/Audio/Presets/Apple/AUMultibandCompressor/`, but there is no factory preset library shipped as browsable files.

## Notable parameters
- **Bands** — number of active frequency bands (classic multiband use is three; the unit is architected as a four-band compressor).
- **Crossover frequencies** — split points between bands.
- **Threshold / Ratio / Attack / Release / Makeup Gain** — standard dynamics controls, available per band.
- **Lookahead** — how far ahead the processor looks in order to react earlier to peaks; raise it when Peak/RMS is set toward RMS.
- **Peak/RMS** — detection mode. Peak (full left) reacts to short transients; RMS (full right) measures average power over time and behaves more musically. Centered is a good default.

## Quirks
- No custom Apple UI documentation ships with the plugin — the closest official reference is Logic Pro's Multipressor documentation, which shares the same underlying design.
- Parameter behavior can feel unusual compared to third-party multiband compressors (particularly the Peak/RMS + Lookahead interaction). Increase Lookahead as you move toward RMS to avoid sluggish gain reduction.
- Utility/technical unit: has no character coloration or saturation — it is a clean, transparent dynamics tool, not a vibe processor.
- Host UI is a generic parameter list unless the host provides a custom view.

## Common recipes
Not applicable — this is a corrective/utility effect, not a sound-design instrument.
