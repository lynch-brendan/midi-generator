---
name: AURogerBeep
verified: false
last_updated: 2026-09-16
---

# AURogerBeep

Apple's built-in Audio Unit effect that injects a walkie-talkie-style "roger beep" tone whenever the incoming signal drops below a set threshold.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API. It ships as a built-in system component on macOS (installed to `/System/Library/Components/` or `/Library/Audio/Plug-Ins/Components/`) and has no user-facing factory preset library.

## Notable parameters
- **In Signal Db** — threshold level below which the roger beep is triggered.
- **Sensitivity** — how responsively the beep engages relative to the input envelope.
- **Beep Frequency** — pitch of the beep tone (Hz).
- **Robotic** — toggles a more robotic/modulated beep character.

(Parameter names are inferred from Apple's `kRogerBeepParam_*` audio unit constants; exact ranges are not documented publicly.)

## Quirks
- Silent/inaudible until the input signal actually falls under the threshold, so on continuous full-level material it will produce nothing. Send it a signal with gaps or automate the input level to hear the beep.
- Marked as a "quirky" utility effect — most producers consider it a novelty/SFX tool rather than a musical processor.
- On recent macOS releases (notably with Final Cut Pro 11 on Apple Silicon) AURogerBeep has been flagged by AU validation as incompatible and excluded by some hosts; behavior in a given DAW is not guaranteed.
- It is an effect (not an instrument) and expects an audio input stream — it will not generate anything on its own.
