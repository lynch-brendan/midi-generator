---
name: AUSampler
verified: false
last_updated: 2026-10-01
preset_paths:
  - "~/Library/Audio/Presets/Apple/AUSampler:.aupreset"
---

# AUSampler

Apple's built-in Core Audio sampler instrument (AudioUnit), available on macOS (10.7+) and iOS (5.0+), that organises sample recordings into a playable, MIDI-driven instrument.

## Presets on disk
User-saved presets are stored as `.aupreset` (Property List) files at:
`~/Library/Audio/Presets/Apple/AUSampler/`

AUSampler can also load instruments from:
- `.aupreset` — native format (text/plist)
- `.dls` / DLS2 — Downloadable Sounds sound banks
- `.sf2` — SoundFont 2 (support varies; some host/API paths check only for `.sf2` extension)
- `.exs` — Logic/GarageBand EXS24 instrument files (macOS 10.8+ / iOS 6+), though complex EXS24 instruments using newer Logic features may not import correctly
- Individual audio files (`.wav`, `.aiff`, `.caf`, `.mp3`) assembled into a custom preset

## Notable parameters
| ID | Name | Range | Default | Notes |
|----|------|--------|---------|-------|
| 900 | Gain | -90 → +12 dB | 0 dB | Global output level |
| 901 | Coarse Tuning | -24 → +24 semitones | 0 | Global pitch shift in semitones |
| 902 | Fine Tuning | -99 → +99 cents | 0 | Global pitch trim in cents |
| 903 | Pan | -1.0 → +1.0 | 0 | Global stereo pan |
| 1000–1007 | Performance Parameter 01–08 | 0.0–1.0 or -1.0–1.0 | unmapped | Per-preset configurable; can be mapped in the AU Lab GUI to envelope attack, filter cutoff, LFO rate, etc. Default state controls nothing. |

Internal subcomponent parameters (oscillator pitch, filter cutoff & resonance, envelope stages, LFO rate) can also be modified at runtime via Group Scope parameter writes or MIDI CC, but these are not surfaced as standard AU parameter IDs — they require undocumented `AudioUnitSetProperty` calls with hidden property IDs.

## Quirks
- **Silent until an instrument is loaded.** The plugin produces no sound if no sample/preset has been loaded. The default state is essentially a placeholder with a built-in sine tone at 440 Hz (`Sine-440 Built-in`) that must be deleted when building custom instruments.
- **Preset file path breakage.** `.aupreset` files embed absolute sample file paths. On project migration or device transfer, paths frequently need manual correction; the system falls back to searching the app bundle, `NSLibraryDirectory`, and `NSDocumentsDirectory` in order.
- **SF2 / DLS import reliability.** The GUI claims to support SoundFont and DLS import, but in practice these format conversions often fail or produce incorrect results. Native `.aupreset` is the most reliable format.
- **EXS24 partial compatibility.** Complex EXS24 instruments using Logic Pro X-specific features may not load correctly.
- **SoundFont preset-save regression.** Saved presets referencing SF2 files can silently fail to reload after closing and reopening the host (GarageBand, Logic), reverting to "failed to load" even when the file exists.
- **Crash on dealloc before engine attach (AVAudioUnitSampler wrapper).** Deallocating the sampler before attaching it to an AVAudioEngine causes an assertion crash (`unbalanced reference count`).
- **Loop-point clicks.** Audio files longer than ~2.5 seconds used with loop points may produce audible clicks on playback.
- **Performance Parameters default to unmapped.** Parameters 1000–1007 have no effect unless explicitly configured per-preset in AU Lab; there is no factory assignment.
- **Sparse official documentation.** Apple's own docs cover only the four global parameters; subcomponent control relies on undocumented property IDs and community reverse engineering.
- **`.aupreset` format is undocumented.** The plist schema is not officially described; editing is done via Xcode's Property List editor or third-party tools.

## Common recipes (optional)
AUSampler has no built-in synthesis; all sound depends on the sample content loaded. Generic recipes are not applicable — load an appropriate `.aupreset`, `.sf2`, `.exs`, or audio file set for the desired timbre.
