---
name: AUMatrixReverb
verified: true
last_updated: 2026-09-11
---

# AUMatrixReverb (Apple)

Apple's built-in matrix reverb. Ships with every macOS. High-quality
algorithmic reverb — cathedral / hall / plate / room styles.

## Presets

Exposes ~15 factory presets via the standard AU API. Names like:
"Small Room", "Medium Room", "Large Room", "Medium Hall", "Large Hall",
"Cathedral", "Plate 1", "Plate 2".

## Notable parameters

- **Dry/Wet Mix** — main sound-shaping knob for "more/less reverb."
- **Small/Large Delay**, **Small/Large Density**, **Small/Large Absorption**
  Frequency — fine-tuning the reverb character.
- **RT60 Time** (frequency-dependent) — decay time.

## Recipes

- For a subtle vocal reverb: preset "Medium Room", Dry/Wet ~0.15.
- For a big pad reverb: preset "Cathedral", Dry/Wet ~0.35.
- To dial back an existing reverb without swapping the preset: lower the
  Dry/Wet Mix parameter via `set_plugin_param`.
