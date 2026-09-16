---
name: AUSpatialMixer
verified: false
last_updated: 2026-09-16
---

# AUSpatialMixer

Apple's built-in Audio Unit for 3D spatial audio rendering using HRTF (Head-Related Transfer Function), intended for developer/system use rather than music production.

## Presets on disk
Not applicable — no factory preset library. This is a system-provided Apple Audio Unit (subtype `aumx 3dem appl`) exposed via the AudioUnit API.

## Notable parameters
- **Azimuth** — horizontal angle of the source around the listener
- **Elevation** — vertical angle of the source
- **Distance** — distance from the listener (drives attenuation curve)
- **Gain / MinGain / MaxGain** — level and level-range controls
- **GlobalReverbGain / ReverbBlend** — send/mix into the spatial reverb
- **ObstructionAttenuation / OcclusionAttenuation** — environmental attenuation
- **PlaybackRate** — source playback rate
- **Attenuation Curve** — Linear, Exponential, Inverse, or Power (set via `kAudioUnitProperty_SpatialMixerAttenuationCurve`)

## Quirks
- This is a **system/developer Audio Unit**, not a user-facing music plugin. It generally does not present a GUI in a DAW and is designed to be driven programmatically via the AudioUnit API (`AVAudioEnvironmentNode`, `AUSpatialMixer*` properties).
- Most music DAWs will list it under Apple mixers but it is not intended for typical mixing/production workflows — it is meant for spatial/VR/game audio rendering with HRTF.
- Behavior depends on configured output type (headphones/HRTF vs. multichannel) and rendering flags — many parameters have no audible effect unless the corresponding rendering flag is enabled.
- Not recommended for a music-production assistant to auto-load.
