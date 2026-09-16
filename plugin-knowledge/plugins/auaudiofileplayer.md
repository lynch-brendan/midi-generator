---
name: AUAudioFilePlayer
verified: false
last_updated: 2026-09-16
---

# AUAudioFilePlayer

Apple's built-in AudioUnit generator that plays back audio files from disk with scheduled region playback.

## Presets on disk
Not applicable — this is a system Apple AudioUnit generator, not a user-facing plugin with a factory preset library. It is typically driven programmatically via the AudioUnit API (scheduling file regions, start times, and playback rate).

## Notable parameters
- **Scheduled Files** — the audio file(s) to be played (set via API, not a knob).
- **Scheduled Start Time** — sample-accurate start time for playback.
- **Playback Rate / Region** — region of the file to play and rate scalar.

(Note: AUAudioFilePlayer exposes most of its control surface through AudioUnit property calls rather than user-facing automatable parameters. A DAW hosting it as a generic AU generator will usually show few or no knobs.)

## Quirks
- **Silent until a file is scheduled.** With no file assigned and no start time scheduled, it produces no output — a DAW inserting it blind will hear nothing.
- **Not a musical instrument.** It does not respond to MIDI notes; it plays back a pre-loaded audio file, similar to a file-player utility rather than a sampler.
- **System AU, developer-oriented.** Intended primarily for app developers using Core Audio, not for music production. Most DAWs (Logic, Ableton, Reaper on macOS) either hide it or list it under generic/utility AUs.
- **No factory sounds, no GUI worth speaking of** in most hosts.

## Common recipes (optional)
Not applicable — this plugin has no musical character of its own; it simply plays whatever audio file it is pointed at.
