---
name: Serato Sample
verified: true
last_updated: 2026-09-11
---

# Serato Sample

Sampler by Serato. Chops, pitches, and time-stretches a loaded audio sample.
No factory sound library — starts silent until a sample is dropped in.

## Presets

**Serato Sample has NO factory preset browser.** Its state IS the loaded
sample + settings. Do not try to pick a preset by name for this plugin —
the concept doesn't apply.

## Loading a sample

A sample can be loaded programmatically by feeding the plugin state (which
includes the sample path or embedded sample data) via VST3 `setStateInformation`.
Sample state is per-instance — every fresh channel starts empty.

For MVP: instruct the user to drag a sample into Serato Sample's window
directly. Nasty can't discover their sample library from disk.

## Notable parameters

- **Pitch** — semitones up/down from source.
- **Attack / Decay / Sustain / Release** — envelope shaping.
- **Start / End** — sample slice boundaries.
- **Reverse** — plays sample backwards.

## Quirks

- **Completely silent until a sample is loaded.** If you load Serato Sample
  onto a channel and there's no sound, this is expected — user needs to
  drop a sample in.
- Not suitable for melodic instrument requests ("trumpet", "violin") — use
  a GM instrument for that.
