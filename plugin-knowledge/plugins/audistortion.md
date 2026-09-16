---
name: AUDistortion
verified: false
last_updated: 2026-09-16
---

# AUDistortion

Apple's built-in macOS AudioUnit multi-stage distortion effect combining delay, ring modulation, decimation, and waveshaping distortion.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU factory preset API. AUDistortion is a system-provided Apple Audio Unit (subtype `dist`, manufacturer `appl`) bundled with macOS Core Audio.

## Notable parameters
Parameters are exposed via the standard AudioUnit parameter API. Documented parameter IDs include:

- **Delay** (ms, 0.1 → 500, default 0.1) — pre-distortion delay time
- **Decay** (rate, 0.1 → 50, default 1.0) — delay decay/feedback
- **Delay Mix** (%, 0 → 100, default 50) — dry/wet for the delay stage
- **Ring Mod Freq 1** (Hz, 0.5 → 8000, default 100) — first ring modulator carrier
- **Ring Mod Freq 2** (Hz, 0.5 → 8000, default 100) — second ring modulator carrier
- **Ring Mod Balance** (%, 0 → 100, default 50) — balance between the two ring mod carriers
- **Ring Mod Mix** (%, 0 → 100, default 0) — dry/wet for the ring modulator stage
- **Decimation** (%, 0 → 100, default 50) — bit/sample-rate decimation amount
- **Rounding**, **Decimation Mix**, **Linear Term**, **Squared Term**, **Cubic Term**, **Polynomial Mix**, **Final Mix**, **Softclip Gain** (dB) — waveshaping/distortion stage controls

(Parameter list based on Apple's `AUDistortion` parameter enum as documented in the Core Audio headers / AudioKit dev tools mirror.)

## Quirks
- This is an Apple system Audio Unit — it is macOS-only and not available as VST3 or on Windows.
- Component identifier: type `aufx`, subtype `dist`, manufacturer `appl`.
- Multi-stage: signal passes through delay → ring modulator → decimator → polynomial waveshaper → soft-clip. Some "distortion" presets rely mostly on the ring mod or decimator rather than the waveshaper, so tweaking a single knob may not behave as expected.
- Ring Mod Mix defaults to 0 (ring mod inaudible until raised). Delay Mix defaults to 50, so a slap-back delay is audible on the default patch.
- No custom GUI in most hosts — parameters are typically shown as a generic AU parameter list.
- Factory presets are exposed through the AU factory preset API (`kAudioUnitProperty_FactoryPresets`), not as user-accessible files.
