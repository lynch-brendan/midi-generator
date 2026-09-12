---
category: Stereo
type: effect
---

# Stereo Tools

Width control — make it wider, narrow it, mid/side processing, panning tricks. Reach for these on "make it wider," "narrow the low end," "spread it out," "mid/side," "pan," "stereo image."

## Options

### Surge XT Effects — Stereo algorithms (Rotary, Ensemble, Chorus can widen)

- **Character:** thickens and widens the source signal via modulation-based stereo spread
- **Best for:** widening synths and pads, adding movement across the stereo field
- **Emotional tags:** wide, moving, dreamy
- **How to use:** `add_plugin_effect(channel_id="<target>", plugin_id="<Surge XT Effects id>")` then `set_plugin_param` with `param_name="FX Type"` to select a stereo-affecting algorithm. See `plugins/surge-xt-effects.md`.

## Common recipes

- **Widen a mono pad:** Surge Effects → Chorus or Ensemble, moderate depth.
- **Rotary width on organ:** Surge Effects → Rotary, alternate slow/fast speeds.

## Comparisons

No dedicated stereo tools available currently — we're leaning on modulation effects to create width.

## What we're missing

- No dedicated stereo widener (Voxengo MSED, iZotope Ozone Imager 2 free)
- No true mid/side processor
- No panning/auto-pan LFO effect

**Recommendation:** if the user needs precise stereo control (e.g., "narrow the bass, widen the highs"), we can't currently do it well — bundling a free stereo tool would fix this gap.
