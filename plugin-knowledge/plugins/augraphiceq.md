---
name: AUGraphicEQ
verified: false
last_updated: 2026-09-16
---

# AUGraphicEQ

Apple's built-in Audio Unit graphic equalizer, bundled with macOS as part of the system Audio Units.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API.

## Notable parameters
- **Number of Bands** — switchable between 10-band and 31-band modes
- **Per-band gain sliders** — cut/boost each ISO frequency band (typically ±dB)

## Quirks
- Ships with macOS as a system Audio Unit (Apple manufacturer, `appl`); not available on Windows and not offered in VST3 format.
- Two operating modes (10-band vs 31-band) change the parameter count dynamically — automation mappings must account for the current mode.
- Utility-grade EQ intended for corrective/tone-shaping work; no analog modeling, saturation, or coloration — it is a clean, transparent graphic EQ.
- Zero-latency, minimal CPU; suitable as a quick tone-shaping insert but lacks the surgical control of a parametric EQ.
