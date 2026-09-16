---
name: AUMixer
verified: false
last_updated: 2026-09-16
---

# AUMixer

Apple's system-supplied Audio Unit mixer component (kAudioUnitType_Mixer) — a developer/utility routing unit, not a musical effect intended for creative use.

## Presets on disk
Not applicable — no factory preset library. AUMixer is a system-level component used programmatically via AUGraph / AVAudioEngine; it is not distributed as a user-facing plugin with presets.

## Notable parameters
Parameters depend on which mixer subtype is instantiated:
- **StereoMixer** (`kAudioUnitSubType_StereoMixer`): volume, pan
- **MultiChannelMixer** (`kAudioUnitSubType_MultiChannelMixer`): volume, pan, enable (per input bus + output bus)
- **MatrixMixer** (`kAudioUnitSubType_MatrixMixer`): volume, enable (no pan; routes any input channel to any output channel)
- **SpatialMixer** (`kAudioUnitSubType_SpatialMixer`): Azimuth, Elevation, Distance, Gain, MinGain/MaxGain, PlaybackRate, ReverbBlend, GlobalReverbGain, Obstruction/OcclusionAttenuation
- **3DMixer** (`kAudioUnitSubType_3DMixer`, legacy)

Manufacturer: `kAudioUnitManufacturer_Apple`.

## Quirks
- Not a creative plugin — this is Apple's low-level mixer AU used by developers building audio graphs. It typically has no GUI and will not appear in most DAW plugin browsers as a musical processor.
- MatrixMixer defaults all volumes to 0; you must iterate every input/output bus and set volume before any audio passes through.
- Different subtypes expose different parameter sets (see above), so automation code cannot assume a common parameter map.
- SpatialMixer / 3DMixer are for positional audio (games, AR/VR), not stereo music mixing.
- Not intended to be hosted as a track insert in a DAW for tone-shaping — it does not add color, saturation, or musical character.
