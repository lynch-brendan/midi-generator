---
name: AUHipass
verified: false
last_updated: 2026-09-16
---

# AUHipass

Apple's built-in AudioUnit high-pass filter effect, bundled with macOS Core Audio.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API.

## Notable parameters
- **Cutoff Frequency** (Hz) — frequencies below this point are attenuated
- **Resonance** (dB) — emphasis/peak at the cutoff frequency

## Quirks
- System-provided Apple AU; only available on macOS in AU-hosting DAWs (Logic, GarageBand, Reaper w/ AU, etc.). No VST3 version.
- Utility-grade filter with no character coloration — it's a clean mathematical high-pass, not a musical/analog-modeled filter.
- Minimal UI (generic AU parameter view in most hosts) — designed for functional use, not sound design.
- Very low CPU; safe to instantiate many times.
