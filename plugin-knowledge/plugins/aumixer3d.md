---
name: AUMixer3D
verified: false
last_updated: 2026-09-16
---

# AUMixer3D

Apple's system-supplied 3D Mixer AudioUnit (subtype `kAudioUnitSubType_3DMixer` / `aumx 3dmx appl`) — a developer-facing Core Audio mixer for spatializing mono sources in 3D space, not a user-facing musical plugin.

## Presets on disk
Not applicable — no factory preset library. AUMixer3D is a built-in system AudioUnit exposed by macOS Core Audio for use by app developers (e.g., it historically underpinned OpenAL on iOS). It has no file-based presets and is not intended to be loaded from a DAW's plugin menu as a musical processor.

## Notable parameters
Controlled programmatically via the Audio Unit API rather than a GUI:
- **k3DMixerParam_Azimuth** — horizontal angle of the source relative to the listener (used for stereo panning; ±90° = hard left/right).
- **k3DMixerParam_Distance** — apparent distance from listener (must be a non-zero positive value, e.g. 1.0, for azimuth changes to take effect).
- **k3DMixerParam_Gain** — per-bus gain scaling of the audio data itself (spatial attenuation is handled separately via Distance).
- **k3DMixerParam_PlaybackRate** — per-bus pitch/playback rate.
- **kAudioUnitProperty_UsesInternalReverb** — enables the internal reverb (off by default); once enabled, per-bus reverb is switched on via `k3DMixerRenderingFlags_DistanceDiffusion`.
- **ReferenceDistance / MaximumDistance / Attenuation** — distance-model parameters used to clamp per-bus volume based on 3D position.

## Quirks
- Not a plugin a musician loads in a DAW — it is a Core Audio system component with no built-in UI, driven entirely via `AudioUnitSetProperty` / `AudioUnitSetParameter`.
- Input buses only accept **mono LPCM** streams; stereo sources must be split into two independent mono buses.
- **Distance must be > 0** (e.g. 1.0) before azimuth changes have any audible effect.
- Output channel layouts are limited (historically stereo, quad, and 5.0 in the v2.0 3DMixer); channel layout should be set explicitly to match the stream format or an error is returned.
- Largely superseded by **AUSpatialMixer** (`kAudioUnitSubType_SpatialMixer`, added in iOS 8 / modern macOS), which is Apple's current recommendation for new development.
- On iOS, Apple's guidance has long been that if you need 3D-mixer features, use **OpenAL** (itself implemented on top of the 3D Mixer) rather than the audio unit directly.
- Not suitable for use as a musical/creative plugin in this registry.
