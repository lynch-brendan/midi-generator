---
name: AUNBandEQ
verified: false
last_updated: 2026-09-16
---

# AUNBandEQ

Apple's built-in system Multitype N-Band Equalizer AudioUnit (Apple: AUNBandEQ) — a clean, flexible multi-band parametric EQ shipped with macOS/iOS Core Audio.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program/state API (host-managed). It ships with no notable factory preset library of its own; it is a system-provided processor typically driven manually or by host presets.

## Notable parameters

- **Number of bands** — <cite index="15-10">up to 16 bands</cite> can be enabled independently.
- **Filter type (per band)** — <cite index="15-10">Parametric (freq, BW, gain), Butterworth LP (freq), Butterworth HP (freq), Resonant LP (freq, BW), Resonant HP (freq, BW), Bandpass (freq, BW), Bandstop (freq, BW), Low shelf (freq, gain), High shelf (freq, gain), Resonant Low shelf (freq, BW, gain), Resonant High shelf (freq, BW, gain)</cite>.
- **Frequency (per band)** — <cite index="15-8">up to half the sample rate, at 3 decimals of precision</cite>.
- **Bandwidth / Q (per band)** — specified as **bandwidth in octaves**, not Q; <cite index="15-8">BW < 5, 2-decimal precision</cite>. Note: users converting from a Q value must convert Q↔BW themselves.
- **Gain (per band)** — <cite index="15-8">−96 to +24 dB, 1-decimal precision</cite>.
- **Bypass (per band)** — each band can be individually enabled/disabled.

## Quirks

- Bandwidth is expressed in **octaves (BW), not Q**. <cite index="7-3,7-4,7-5">Users importing filter settings from tools like REW have reported needing a Q→BW conversion, and in some hosts the entered values produce no audible change</cite> — always verify with a measurement or sweep.
- The parametric filter behavior <cite index="4-14">appears to use a constant-Q definition</cite>, but Apple does not document this definitively — bandwidth vs. gain interaction should be checked if precise curve matching matters.
- <cite index="15-8">Sample-rate support observed at 44.1, 48, 88.2 and 96 kHz</cite>; the max frequency scales to Nyquist.
- No built-in analyzer/spectrum display in the stock UI — this is a functional utility EQ, not a modern visual EQ like Pro-Q.
- Available on macOS/iOS out of the box; it is <cite index="8-4,8-5,8-6,8-7">one of the "hidden" system audio units also known from GarageBand on macOS/iOS, and can be exposed to AUv3 hosts via third-party wrappers when a host does not surface UI-less system units</cite>.
- Not available on Windows — AU-only, macOS/iOS only.
