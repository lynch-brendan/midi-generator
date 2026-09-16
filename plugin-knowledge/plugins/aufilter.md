---
name: AUFilter
verified: false
last_updated: 2026-09-16
---

# AUFilter

Apple's built-in AudioUnit combining a low-frequency (low shelf/high pass) and high-frequency (high shelf/low pass) filter section.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API.

## Notable parameters
- Low Frequency (Hz)
- Low Gain (dB) — shelf boost/cut for the low band
- High Frequency (Hz)
- High Gain (dB) — shelf boost/cut for the high band

(Parameter names are approximate; AUFilter is a minimal Apple-supplied unit with no dedicated GUI in most hosts.)

## Quirks
- Ships with macOS as part of Apple's built-in Audio Units — no installer required.
- Considered obscure/minimal; one contemporary review described it as effectively a combined low-shelf/high-pass plus high-shelf/low-pass, and "not all that useful" compared to AUParametricEQ or AUNBandEQ.
- Fails Apple AU validation in some hosts (e.g., Final Cut Pro X has been reported to exclude it along with other Apple AUs).
- No custom GUI in most third-party hosts — presents a generic parameter list.
- Prefer AUNBandEQ or AUParametricEQ for most tone-shaping tasks.
