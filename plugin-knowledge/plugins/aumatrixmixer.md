---
name: AUMatrixMixer
verified: false
last_updated: 2026-09-16
---

# AUMatrixMixer

Apple's built-in Audio Unit matrix mixer — routes N input channels to M output channels with per-crosspoint, per-input, and per-output gain control.

## Presets on disk
Not applicable — this is an Apple system Audio Unit utility (kAudioUnitSubType_MatrixMixer) with no factory preset library. Configuration is done programmatically or via the host's routing UI.

## Notable parameters
- **Crosspoint Volume** — gain at each (input, output) intersection in the matrix
- **Input Volume** — per-input-channel gain
- **Output Volume** — per-output-channel gain
- **Global Volume** — master gain across the whole matrix
- **Enable** — per-input and per-output enable/bypass flags
- **Meter (read-only)** — post-gain level metering per channel

## Quirks
- Not a musical/creative effect — this is a low-level routing/mixing utility exposed by Core Audio, primarily intended for developers building audio graphs (AUGraph / AVAudioEngine).
- Bus/channel counts must be configured before use; the matrix has no meaningful default routing and will pass silence until crosspoints are set.
- Most DAWs either hide this AU or expose it only as an advanced routing node; it has no creative sound-shaping parameters.
- No factory presets, no GUI in most hosts (parameter-list view only).
