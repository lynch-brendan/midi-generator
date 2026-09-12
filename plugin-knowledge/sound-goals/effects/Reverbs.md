---
category: Reverbs
type: effect
---

# Reverbs

Space and depth effects — halls, rooms, plates, cathedrals. Reach for these on "add reverb," "make it bigger," "space," "wet," "cathedral," "hall," "room."

## Options

### AUMatrixReverb (Apple, ships with macOS)

- **Character:** clean, transparent, algorithmic reverb — hall/plate/room shapes
- **Best for:** vocals, acoustic instruments, orchestral tails, general-purpose reverb
- **Emotional tags:** natural, spacious, professional
- **Presets:** Small Room, Medium Room, Large Room, Medium Hall, Large Hall, Cathedral, Plate 1, Plate 2
- **How to use:** `add_plugin_effect(channel_id="<target>", plugin_id="<AUMatrixReverb id>", preset_name="<preset>")`. Common recipes: subtle vocal reverb = "Medium Room" at Dry/Wet ~0.15; big pad reverb = "Cathedral" at Dry/Wet ~0.35.
- **Detail sheet:** `plugins/aumatrixreverb.md`

### Surge XT Effects — Reverb algorithms

- **Character:** varies by algorithm — Room 1/2, Hall, Plate, Shimmer, Freeze reverbs
- **Best for:** creative/lush reverbs, cinematic tails, shimmer effects on pads
- **Emotional tags:** dreamy, cinematic, ethereal (esp. Shimmer)
- **How to use:** `add_plugin_effect(channel_id="<target>", plugin_id="<Surge XT Effects id>")` then `set_plugin_param` with `param_name="FX Type"` to select reverb algorithm. See `plugins/surge-xt-effects.md` for the generic-parameter quirk.
- **Note:** Surge Effects use generic "FX Parameter 1..N" names — the AI needs to know which FX Type is loaded to interpret them.

## Comparisons

- **AUMatrixReverb vs Surge XT Effects reverb:** AUMatrixReverb is simpler (clean, transparent, preset-driven). Surge Effects reverbs are more creative but harder to automate because of the generic-param naming.
- **Small Room vs Large Hall:** small room = tight, close, natural. Large hall = big, cinematic, long tail.
- **Plate vs Hall:** plate = brighter, denser, vintage; hall = fuller, more natural.

## Common recipes

- **Vocal reverb (subtle, professional):** AUMatrixReverb "Medium Room", Dry/Wet ~0.15.
- **Big pad reverb:** AUMatrixReverb "Cathedral", Dry/Wet ~0.35.
- **Drum room reverb:** AUMatrixReverb "Small Room" or "Medium Room" for adding depth without washing out.
- **Shimmer pad reverb:** Surge XT Effects with FX Type set to a shimmer algorithm on a pad channel.

## What we're missing

No Valhalla Supermassive (free industry-standard shimmer/large-space reverb). No TAL-Reverb-4 (free plate). No OrilRiver. Adding those in the bundle would dramatically expand reverb color options.
