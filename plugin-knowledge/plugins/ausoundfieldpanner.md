---
name: AUSoundFieldPanner
verified: false
last_updated: 2026-09-16
---

# AUSoundFieldPanner

Apple-bundled AudioUnit panner plug-in (subtype `aupn ambi appl`) that positions a mono/stereo source within an ambisonic-style 3D sound field for surround/spatial output.

## Presets on disk
Not applicable — no factory preset library. Presets (if any) are exposed via the standard AU program API.

## Notable parameters
- Azimuth — horizontal angle of the source around the listener
- Elevation — vertical angle of the source relative to the listener
- Distance / Radius — distance of the source from the listener
- (Panner units expose parameters via the AU kAudioUnitProperty_3DMixerAttenuationCurve / panner property API rather than a rich custom UI)

## Quirks
- This is an Apple developer sample/demo panner unit shipped with macOS since Leopard (10.5), intended primarily to demonstrate the panner-unit starting point for AU developers.
- It is a **panner-type Audio Unit** (`aupn`), not a standard effect (`aufx`). Many DAWs (including Logic Pro) do not list panner-type AUs in their normal insert-effect menus, so it may not appear in the plug-in browser of a typical music host.
- Requires a multi-channel / surround output bus configuration to produce meaningful results; on a plain stereo bus its behavior is limited.
- No GUI in most hosts — parameters are accessed via the generic AU parameter view.
- Not intended as a musical/creative panner; it is a utility for spatial audio positioning.
