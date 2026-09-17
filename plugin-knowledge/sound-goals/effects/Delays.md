---
category: Delays
type: effect
---

# Delays

Echo and repeat effects — slap delay, ping-pong, tempo-synced dub delay, tape delay. Reach for these on "add delay," "echo," "ping pong," "dub delay," "tape echo."

## Options

### Airwindows Consolidated

- **Character:** Warm, tape-flavored delays and ambience processors; includes tape-style delay (TapeDelay, TapeDelay2), pitch-shifted delay (PitchDelay), sample-accurate delays (SampleDelay, PurestEcho), and ADT (Automatic Double Tracking) for vintage doubling effects.
- **Best for:** Vintage tape echo on vocals and guitars, ADT doubling for width, rhythmic delay throws, sample-offset stereo placement.
- **Emotional tags:** Vintage, warm, retro, spacious, intimate.
- **Comparison:** TapeDelay has a characterful tape-flutter quality reminiscent of hardware tape echo units; less feature-rich than dedicated delay plugins (no sync grid, no tap tempo in most algorithms) but more characterful than transparent digital delays.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="Airwindows Consolidated", parameters={"algorithm": "TapeDelay2"})` for tape echo, or `"algorithm": "ADT"` for vintage doubling.

### AUDelay

- **Character:** Clean, plain, transparent digital delay with a lowpass-filtered feedback path for gently darkening repeats. No modulation, no analog coloration — a utilitarian "just a delay" sound.
- **Best for:** Simple single-tap echoes, slapback thickening on vocals/guitars/organs, and short-time comb-filter/flanger-style tonal effects (delay times of ~0.0001–0.0099 s with 50% mix and zero feedback). Good as a lightweight always-available fallback when no third-party delay is installed.
- **Emotional tags:** neutral, dry, functional, vintage-basic, no-frills
- **Comparison:** Much simpler and more dated than Logic's Stereo Delay, Tape Delay, Delay Designer, or the TieDye Delay in Pedalboard; lacks the warmth of a tape/analog emulation and the rhythmic power of tempo-synced or ping-pong delays. Closer in spirit to a mono textbook digital delay line than to a musical "character" delay.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUDelay", preset_name="...")`

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
