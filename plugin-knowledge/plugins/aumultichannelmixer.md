---
name: AUMultiChannelMixer
verified: false
last_updated: 2026-09-16
---

# AUMultiChannelMixer

Apple's built-in Core Audio multichannel mixer Audio Unit — a developer/system utility that sums multiple input buses into a single output, exposed as an AU component (type `aumx`, subtype `mcmx`, manufacturer `appl`).

## Presets on disk
Not applicable — no factory preset library. This is a system Audio Unit intended for programmatic use in AUGraph/AVAudioEngine setups; it exposes only per-bus volume/enable parameters via the standard AU parameter API.

## Notable parameters
- **Input Bus Volume** (per input element) — gain for each input bus.
- **Input Bus Enable** — on/off toggle per input bus.
- **Output Volume** — master output gain.
- **Pan** (per input, where supported) — stereo placement of each input.

## Quirks
- This is a **system/utility Audio Unit shipped by Apple with macOS/iOS Core Audio**, not a musical mixer plugin. Most DAWs either hide it or list it under Apple utilities; loading it on a track typically does nothing useful because its input bus count must be configured programmatically before any audio will flow.
- Number of input buses must be set via `kAudioUnitProperty_ElementCount` before initialization; hosts that don't do this will get silence or a single pass-through bus.
- Intended primarily for developers building audio graphs with `AVAudioEngine`/`AUGraph`, not for use as a track insert in a DAW.
- No GUI beyond the generic AU parameter view in most hosts.

## Common recipes (optional)
Not applicable — utility component, no musical presets.
