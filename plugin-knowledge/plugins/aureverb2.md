---
name: AUReverb2
verified: false
last_updated: 2026-09-16
---

# AUReverb2

Apple's built-in AudioUnit reverb (v2), a system-provided algorithmic reverb originating from the iOS audio unit set and also available on macOS hosts.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API (no file-based factory library). Apple's system Audio Units are UI-less by default; some hosts show no editor, others (e.g. GarageBand, Logic) provide a generic control panel.

## Notable parameters
Based on Apple's AudioUnit parameter definitions (`kReverb2Param_*`):

- **DryWetMix** — Global crossfade, 0–100 (%), default 100. Balance between dry input and reverb tail.
- **Gain** — Global, -20 to +20 dB, default 0. Output gain trim.
- **MinDelayTime** — Global, 0.0001–1.0 s, default 0.008. Minimum early-reflection delay.
- **MaxDelayTime** — Global, 0.0001–1.0 s, default 0.050. Maximum early-reflection delay (shapes room size / density).
- **DecayTimeAt0Hz** — Global, 0.001–20.0 s, default 1.0. Low-frequency reverb tail length.
- **DecayTimeAtNyquist** — Global, 0.001–20.0 s, default 0.5. High-frequency tail length (lower = darker/damped tail).
- **RandomizeReflections** — Global integer, 1–1000, default 1. Randomization seed for early reflections.

## Quirks
- Apple's system Audio Units are traditionally **UI-less**; many third-party AU hosts show no editor. On macOS, hosts like Logic/GarageBand present a generic slider panel. Wrapper products (e.g. "WU: AUReverb2") exist specifically to expose the UI in hosts that don't render UI-less units.
- Default DryWetMix is 100 (fully wet) — insert on a bus/aux or reduce mix on an insert channel to avoid losing the dry signal.
- Parameter IDs and ranges come from the iOS reverb unit definition; ranges must be respected or the AU will clamp/reject values.
- No named factory presets in the traditional sense — state is saved/recalled through the host's AU preset mechanism (`.aupreset` files if the host writes them).
- Distinct from `AUMatrixReverb` (the older, more parameter-rich Apple reverb) and from Logic's Space Designer / ChromaVerb.
