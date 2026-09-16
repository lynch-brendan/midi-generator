---
name: AUSampleDelay
verified: false
last_updated: 2026-09-16
---

# AUSampleDelay

Apple's built-in macOS AudioUnit that delays a signal by a precise number of audio samples — a utility for sample-accurate alignment, not a creative echo effect.

## Presets on disk
Not applicable — no factory preset library. Presets (if any) are host-managed via the standard AU program API.

## Notable parameters
- **Delay (samples):** Integer number of audio samples to delay the signal. At 44.1 kHz, 44 samples ≈ 1 ms, 441 ≈ 10 ms, 4410 ≈ 100 ms.

## Quirks
- This is NOT a musical delay effect — there is no feedback, no wet/dry mix, no tempo sync, no filtering. Output is 100% wet, delayed dry signal.
- Delay time is specified in **samples**, so the resulting time in milliseconds depends on the current session sample rate. Reusing the same value across sessions at different sample rates will produce different delay times.
- Sibling plugin AUDelay sets delay time in seconds and is what most users want for musical echoes; AUSampleDelay is intended for sample-accurate audio work such as phase alignment, latency compensation, or driver/speaker delay in live sound.
- No GUI in many hosts (Apple ships it as a UI-less utility on macOS); some third-party wrappers exist to expose a UI on iOS.
- On macOS only (AudioUnit format); not available as VST3 or on Windows.
