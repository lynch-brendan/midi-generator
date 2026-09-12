---
name: AUDynamicsProcessor
verified: true
last_updated: 2026-09-11
---

# AUDynamicsProcessor (Apple)

Apple's built-in compressor / expander. Ships with every macOS. Solid
transparent compressor — good for glueing drums, bass, vocals.

## Presets

Exposes ~5 factory presets ("Default", "Slow Comp", "Fast Comp", etc.) via
the standard AU API. Basic but usable.

## Notable parameters

- **Threshold** — level in dB where compression starts (usually -20 to -10 dB).
- **Head Room** — output level after compression.
- **Expansion Ratio / Threshold** — for downward expansion (noise gate).
- **Attack Time**, **Release Time** — envelope response.
- **Master Gain** — post-compression output level.

## Recipes

- Glue bus (drums, master): Threshold -12dB, low ratio, medium attack, fast release.
- Aggressive bass compression: Threshold -18dB, higher ratio, fast attack.
