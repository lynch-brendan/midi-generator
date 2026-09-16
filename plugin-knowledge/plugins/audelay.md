---
name: AUDelay
verified: false
last_updated: 2026-09-16
---

# AUDelay

Apple's stock Audio Unit delay effect bundled with macOS Core Audio, GarageBand, and Logic Pro — a simple, utilitarian digital delay.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API. It is a basic Apple system Audio Unit with no dedicated factory preset library on disk.

## Notable parameters
- **Dry/Wet Mix** — balance between clean and delayed signal (percentage).
- **Delay Time** — delay time in seconds. Accepts very small values (e.g. 0.0001–0.0099 s) suitable for comb-filter effects, up to longer echo times.
- **Feedback** — amount of delayed signal fed back into the input; the middle value on the slider represents 0 (bipolar; negative feedback is also possible).
- **Lowpass Cutoff** — a lowpass filter in the feedback path, up to 22050 Hz maximum, used to darken repeats.

## Quirks
- AUDelay is a very old Apple Audio Unit; it is considered dated compared to Logic/GarageBand's modern delays (e.g. Stereo Delay, Tape Delay, Delay Designer, TieDye Delay in Pedalboard).
- Delay Time has such a wide range that for very small values (comb-filter territory) it is easier to type the value into the text box rather than use the slider.
- The Feedback control is bipolar — the slider midpoint is zero feedback, so "minimum" is not "no repeats."
- Bare-bones UI with no tempo sync, no stereo/ping-pong controls, and no modulation — it is a mono-style single-tap delay. For stereo or tempo-synced work, use a different plugin.
- On modern macOS this AU may not appear in every DAW's plugin browser (some hosts hide legacy Apple utility AUs); in GarageBand it is accessed via Smart Controls → Plug-Ins → Audio Units → Apple.
