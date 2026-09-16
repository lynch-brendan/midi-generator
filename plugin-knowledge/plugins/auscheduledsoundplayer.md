---
name: AUScheduledSoundPlayer
verified: false
last_updated: 2026-09-16
---

# AUScheduledSoundPlayer

Apple system Audio Unit that plays back pre-scheduled audio buffer slices at specified sample-accurate times; part of Apple's Core Audio / AudioToolbox generator units, not a musical instrument.

## Presets on disk
Not applicable — no factory preset library. This is a developer-facing generator AU with no user-facing UI or sound design content.

## Notable parameters
None exposed as musical parameters. The unit is controlled programmatically via Core Audio APIs (scheduling `ScheduledAudioSlice` structs, setting the start time stamp, and providing buffers). There are no knobs, envelopes, or sound-shaping controls.

## Quirks
- Silent by default — produces no output unless a host application programmatically schedules audio slices via the AudioToolbox API.
- Not intended for use inside DAWs as a creative instrument; it appears in the AU list on macOS because it is a registered system component (subtype `sury`, manufacturer `appl`).
- No GUI. Most DAWs will show a generic parameter view with nothing to adjust.
- Cannot load audio files from a browser — buffers must be supplied by host code.
- Included alongside sibling units like AUScheduledSoundPlayer's counterpart AUAudioFilePlayer, which is similarly developer-only.

## Common recipes
Not applicable — this is not a musical instrument. Use a sampler (e.g., AUSampler, Kontakt, DecentSampler) or an audio track for sample playback in a music production context.
