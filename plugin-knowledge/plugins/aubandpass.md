---
name: AUBandpass
verified: false
last_updated: 2026-09-11
---

# AUBandpass

Apple's built-in AudioUnit bandpass filter that ships with macOS, exposing a center frequency and bandwidth control.

## Presets on disk
Not applicable — this plugin exposes presets via the standard VST/AU program API. AUBandpass is a system Audio Unit bundled with macOS and does not ship a user-facing factory preset library on disk; any saved user presets go through the host's standard AU preset mechanism (typically `~/Library/Audio/Presets/Apple/AUBandpass/*.aupreset`).

## Notable parameters
Per Apple's `AudioUnitParameters.h` header:

- **CenterFrequency** — Global, Hz, range 20 → (SampleRate/2), default 5000
- **Bandwidth** — Global, Cents, range 100 → 12000, default 600

## Quirks
- No custom GUI in most hosts — AUBandpass is one of Apple's minimal system Audio Units, so hosts typically render a generic parameter view rather than a branded editor. There is no hidden internal browser to reach into.
- The maximum CenterFrequency depends on the audio unit's sample rate — the upper bound is the Nyquist frequency (SampleRate/2), so a value that's valid at 96 kHz may clip to a lower ceiling at 44.1 kHz.
- Bandwidth is specified in **cents**, not Hz — a common trip-up when automating. 1200 cents = 1 octave.
- AUBandpass and other Apple AU effects don't appear as discrete files in the usual `~/Library/Audio/Plug-Ins/Components` or `/Library/Audio/Plug-Ins/Components` directories; they're provided by the system CoreAudio frameworks, so you can't locate or move the component bundle the way you can with third-party AUs.
- Effect only (not an instrument); the component subtype is `bpas` under manufacturer `appl`.
