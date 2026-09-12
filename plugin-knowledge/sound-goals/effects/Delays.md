---
category: Delays
type: effect
---

# Delays

Echo and repeat effects — slap delay, ping-pong, tempo-synced dub delay, tape delay. Reach for these on "add delay," "echo," "ping pong," "dub delay," "tape echo."

## Options

### Surge XT Effects — Delay algorithms

- **Character:** varies by algorithm — Digital Delay, Analog Delay, Tape Delay, Ensemble delay
- **Best for:** any tempo-synced or free-running delay
- **Emotional tags:** dubby, rhythmic, spacious, vintage (analog/tape variants)
- **How to use:** `add_plugin_effect(channel_id="<target>", plugin_id="<Surge XT Effects id>")` then `set_plugin_param` with `param_name="FX Type"` to select delay algorithm. Tempo sync switch enables musical divisions (1/4, 1/8, 1/8T, etc.).
- **Note:** Surge Effects use generic "FX Parameter 1..N" names — hardcoded to what each FX Type expects. See `plugins/surge-xt-effects.md`.

## Common recipes

- **Vocal slap delay:** Surge XT Effects → Digital Delay, tempo-synced 1/8, low feedback, wet mix ~0.2.
- **Dub echo on snare:** Surge XT Effects → Tape Delay, 1/4 or 3/8, higher feedback, medium wet.
- **Wide ping-pong:** Surge XT Effects → Ensemble/Digital Delay with stereo spread, tempo-synced.

## Comparisons

- **Digital vs Analog vs Tape delay:** Digital = clean/precise; Analog = warmer/slightly detuned; Tape = wobble/saturation.

## What we're missing

No Valhalla FreqEcho (free frequency-shifting delay). No dedicated dub-style delay plugin. No echo/tape saturation combo. Adding Valhalla Freq Echo (free) in the bundle would open modern dub-style workflows.
