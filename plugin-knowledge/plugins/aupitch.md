---
name: AUPitch
verified: false
last_updated: 2026-09-16
---

# AUPitch

Apple's built-in AudioUnit real-time pitch-shifter (macOS/iOS) that changes pitch in cents without changing playback speed.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API. Only a small set of factory algorithm presets (Universal, Complex, Percussive) are provided.

## Notable parameters
- **Pitch (Cents)** — main transposition control; 100 cents = 1 semitone, 1200 cents = 1 octave. Range roughly ±2400 cents (±2 octaves).
- **Effects Blend** — dry/wet mix; at 100 the output is fully pitch-shifted, lower values mix in the original signal.
- **Smoothness** — increases spectral smoothing to reduce certain artifacts (at CPU cost).
- **Tightness** — reduce to remove other kinds of transient/smearing artifacts.
- **Render Quality / Algorithm** — chooses processing quality and/or algorithm type (Universal, Complex, Percussive). Maximum quality is not always the best-sounding choice; Medium can win on some material.

## Quirks
- Hidden inside the Apple Audio Units submenu in most DAWs (Logic, GarageBand, DP, etc.); not exposed in Logic's own plug-in menu.
- Real-time pitch-shift only — it does not do time-stretching. Basic "rough-and-ready" quality by modern standards; third-party algorithms (Serato, iZotope, Celemony) sound better on critical material.
- Automation of the Pitch parameter is coarse in some hosts: values can snap in unpredictable steps (e.g., 0 → +18 → +56 cents) rather than smooth 1-cent increments, making fine automation curves difficult.
- Only three factory presets exist, mapping to the three algorithm types; deeper parameters are largely undocumented by Apple.
- Percussive algorithm is not always best on drums — try the others; results are highly source-dependent.
- Free with macOS/iOS — no install needed, but on some systems the AU is only surfaced through host apps like GarageBand/Logic and may not appear as a standalone .component in `~/Library/Audio/Plug-Ins/Components`.
