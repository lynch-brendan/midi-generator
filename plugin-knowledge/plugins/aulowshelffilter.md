---
name: AULowShelfFilter
verified: false
last_updated: 2026-09-16
---

# AULowShelfFilter

Apple's built-in macOS Audio Unit low-shelf filter — a simple utility EQ that boosts or cuts frequencies below a set cutoff.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API. Apple's system Audio Units do not ship with a factory preset library on disk.

## Notable parameters
- **Cutoff Frequency** (Hz) — the shelf corner frequency, typically 10 Hz to ~200 Hz range for a low shelf
- **Gain** (dB) — amount of boost or cut applied below the cutoff, typically -40 dB to +40 dB

## Quirks
- Ships with macOS as a system Audio Unit (component ID `lshf`/`appl`); available in any AU host without separate installation.
- Very minimal parameter set — this is a utility EQ, not a musical/coloring EQ. No resonance, no drive, no analog modeling.
- Zero gain = effectively bypass; automating gain through 0 is smooth and click-free.
- AU-only; not available as VST3 and not available on Windows.
- Some DAWs hide Apple's built-in AUs by default (e.g., Logic exposes its own EQ instead); you may need to enable "Show Audio Units" or similar.
