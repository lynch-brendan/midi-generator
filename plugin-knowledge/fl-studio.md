---
name: FL Studio
verified: true
last_updated: 2026-09-11
---

# FL Studio (VSTi wrapper)

Image-Line's FL Studio distributed as an AudioUnit — essentially a whole DAW
wrapped as a plugin so it can be hosted inside another DAW.

## Do not use inside Nasty

This plugin is **not suitable for Nasty's use case.** It's designed to host
entire FL Studio projects, not to be a single instrument. Loading it as a
Nasty channel will bring up the full FL Studio interface, which is not
useful for AI-driven song building.

If the user asks for a specific sound, prefer:
- `load_gm_instrument` for realistic instruments.
- Surge XT / Dexed for synth sounds.
- Skip FL Studio VSTi entirely.
