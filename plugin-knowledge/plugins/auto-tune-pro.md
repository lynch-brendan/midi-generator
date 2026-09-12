---
name: Auto-Tune Pro
verified: true
last_updated: 2026-09-11
---

# Auto-Tune Pro (Antares)

Industry-standard pitch correction. Effect — goes on a channel that has an
audio source (usually a vocal recording via mic).

## Presets

Auto-Tune exposes its factory presets via the standard VST3 program API —
the plugin's `presets` array in the manifest is authoritative. Examples:
"Vocal - Lead", "Vocal - Backing", "Classic Auto-Tune", "Robot", etc.

## Notable parameters

- **Retune Speed** (Speed) — how fast pitches snap to the scale. Low
  values (0–20) = obvious Auto-Tune effect. High values (60+) = natural
  correction.
- **Flex-Tune** — how much natural pitch variation gets preserved.
- **Humanize** — adds subtle variation.
- **Key** — the target key/scale (usually C major by default).

## Quirks

- Does nothing on channels without an audio input (i.e. it needs a mic
  recording or an audio clip playing through — pointless on MIDI-only
  synth channels).
