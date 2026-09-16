---
category: Reverbs
type: effect
---

# Reverbs

Space and depth effects — halls, rooms, plates, cathedrals. Reach for these on "add reverb," "make it bigger," "space," "wet," "cathedral," "hall," "room."

## Options

### AUReverb2

- **Character:** Clean, neutral, utilitarian algorithmic reverb. Not colored or lush — sits closer to a generic digital plate/room than to a boutique reverb. Tone can be shaped from bright to dark via the split low/high decay controls.
- **Best for:** Quick, CPU-cheap ambience on any source when a host needs a built-in reverb; sketching/roughing arrangements; iOS/macOS apps that want a system-provided verb without bundling a third-party engine.
- **Emotional tags:** neutral, clean, functional, transparent, unobtrusive
- **Comparison:** Less characterful and less lush than Valhalla VintageVerb or Logic's ChromaVerb; simpler and more generic than Space Designer (which is convolution-based). Comparable in role to a stock DAW reverb — get-the-job-done rather than sound-design centerpiece.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUReverb2", params={"DryWetMix": 30, "DecayTimeAt0Hz": 1.8, "DecayTimeAtNyquist": 0.6, "MaxDelayTime": 0.05})`

### TENSjr

- **Character:** Studio spring reverb modeled after AKG BX-series units; dense, fast-building, plate-like rather than the boingy spring sound of guitar amps. Character fader ranges from splashy/bright to dark and moody.
- **Best for:** Vintage vocal and guitar ambience, drum room/slap, dub/reggae effects, lo-fi and retro production, synth sweetening, short-to-long decays (0.5–20 s) that sit between spring and plate territory.
- **Emotional tags:** vintage, retro, dubby, moody, splashy, atmospheric, nostalgic
- **Comparison:** More plate-like and less "boingy" than typical guitar-amp spring reverbs (e.g. AudioThing Springs, GSi Spring Reverb); simpler and free compared to its bigger sibling TENS (which adds Metallic/Whoosh/Tension, amp drive, 40 s decays, envelope follower); warmer/more colored than clean digital plates like Valhalla Plate.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="TENSjr", params={"Decay": 2.5, "Modulation": 0.3, "Character": 0.5, "Mix": 0.25})`

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
