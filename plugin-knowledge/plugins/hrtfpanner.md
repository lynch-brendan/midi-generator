---
name: HRTFPanner
verified: false
last_updated: 2026-09-16
---

# HRTFPanner

Apple's built-in AudioUnit panner that uses Head-Related Transfer Function (HRTF) convolution to place a mono source in 3D space for binaural (headphone) listening.

## Presets on disk
Not applicable — this is a built-in Apple system AudioUnit (subtype `hrtf`, manufacturer `appl`) with no file-based factory preset library. State is exposed via the standard AU program/parameter API.

## Notable parameters
HRTFPanner is a panner-type AU (`aupn`) and exposes the standard Apple 3D panner parameter set (shared with AUSpatialMixer / spherical / vector panners):

- **Azimuth** — horizontal angle of the source around the listener (degrees).
- **Elevation** — vertical angle of the source relative to the listener (degrees).
- **Distance** — perceived distance from the listener.
- **Gain** — output level.

(Exact parameter IDs and ranges are not publicly documented by Apple beyond the CoreAudio headers; treat parameter names/ranges as approximate.)

## Quirks
- **Not a general-purpose mixer plugin.** HRTFPanner is a panner AU intended to be hosted inside an Apple 3D mixing graph (e.g. AUSpatialMixer / AUMixer3D) with a mono input bus and a stereo (binaural) output bus. Most DAWs (Logic, Ableton, etc.) do not expose it as an insertable effect on a normal stereo track — it typically appears only in developer/host contexts such as Audacity, AU Lab, or custom CoreAudio apps.
- **Headphone-only result.** Output is binaural — designed to be monitored on headphones. On loudspeakers the HRTF cues collapse and it will just sound like a slightly filtered stereo pan.
- **Mono in / stereo out.** Feeding an already-stereo source produces undefined/mixed results; the intended input is a mono point source.
- **No GUI of its own.** As a system AU, it has no custom editor; hosts render a generic parameter list.
- **No factory presets.** State must be set by parameter automation from the host.
- **CPU cost from convolution.** Internally uses FFT convolution with an HRTF impulse-response database, so it is more expensive than a simple pan law.
