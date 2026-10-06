---
name: AUSampler
verified: false
last_updated: 2026-10-06
preset_paths:
  - "~/Library/Audio/Presets/Apple/AUSampler:.aupreset"
  - "/Library/Audio/Presets/Apple/AUSampler:.aupreset"
---

# AUSampler

Apple's built-in Core Audio sampler instrument (AudioUnit), capable of loading `.aupreset`, EXS, DLS2, and SoundFont2 (.sf2) files into a playable, MIDI-driven multi-sample instrument available on macOS and iOS.

## Presets on disk
Presets are stored as `.aupreset` files (plist/XML format) at:
- User: `~/Library/Audio/Presets/Apple/AUSampler/`
- System: `/Library/Audio/Presets/Apple/AUSampler/`

The plugin ships with no factory preset library of its own — presets must be created via AU Lab or programmatically. It can also load EXS24 instruments from Logic/MainStage's sampler instrument directories.

## Notable parameters

| ID | Name | Range | Default | Notes |
|----|------|-------|---------|-------|
| 900 | Gain | −90 → +12 dB | 0 dB | Global output level |
| 901 | CoarseTuning | −24 → +24 semitones | 0 | Global pitch in semitones |
| 902 | FineTuning | −99 → +99 cents | 0 | Global fine-pitch adjustment |
| 903 | Pan | −1.0 → +1.0 | 0 | Global stereo pan |
| 1000–1007 | Performance Parameter 01–08 | −1.0 → +1.0 or 0.0 → 1.0 | unmapped | User-assignable per-preset modulators; can target envelope attack, filter cutoff, LFO rate, etc. Default state controls nothing until mapped in AU Lab. |

Internal (non-discoverable) per-layer parameters accessible only via `AudioUnitSetProperty`:
- Filter cutoff and resonance (per layer)
- DAHDSR envelope stages (per layer, for both amp and filter)
- Oscillator pitch, LFO rate, loop start/end points

## Quirks

- **Silent until a sample/preset is loaded.** The plugin produces no sound and defaults to a built-in sine tone placeholder (`Sine 110 Built-in`) if no valid preset or instrument file is assigned.
- **Performance Parameters 1–8 are unmapped by default** — they control nothing until configured in AU Lab's Performance Parameter Editor and baked into a saved preset.
- **Largely undocumented.** Apple has almost no public documentation for its internal property IDs; most real-time parameter control (filter cutoff, resonance, envelope) requires calling private `AudioUnitSetProperty` IDs reverse-engineered by the community.
- **EXS import is hit-or-miss.** Some Logic/GarageBand EXS24 instruments import successfully; others silently fall back to the default sine tone.
- **No drag-and-drop support.** Audio files cannot be dragged from a DAW's file browser into the AUSampler GUI.
- **Loop-point clicks.** Audio files longer than ~2.5 seconds used with loop points may produce audible clicks on playback; loop points must be set carefully.
- **Sample path resolution is strict.** The `.aupreset` XML references audio files by absolute path; if files are missing at the original path, AUSampler searches only within `Bundle`, `NSLibraryDirectory` (macOS only), `NSDocumentDirectory`, and `NSDownloadsDirectory` — in that order. Broken paths silently fail.
- **AU Lab required for preset editing.** AU Lab (from Apple's "Additional Tools for Xcode" package) is the only native GUI editor for building and saving AUSampler presets.
- **Supports SF2/DLS2.** The plugin can load SoundFont 2 and DLS2 bank files directly in addition to its native `.aupreset` format.
