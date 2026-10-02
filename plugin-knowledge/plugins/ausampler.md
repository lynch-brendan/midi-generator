---
name: AUSampler
verified: false
last_updated: 2026-10-02
preset_paths:
  - "~/Library/Audio/Presets/Apple/AUSampler:.aupreset"
  - "/Library/Audio/Presets/Apple/AUSampler:.aupreset"
---

# AUSampler

Apple's built-in AudioUnit sampler instrument (AUv2), available on macOS and iOS, that plays back audio samples loaded from `.aupreset`, SoundFont/DLS2, EXS24, or raw audio files in response to MIDI.

## Presets on disk

User-saved presets are stored as `.aupreset` files (standard property list format) at:
- `~/Library/Audio/Presets/Apple/AUSampler/` (user domain)
- `/Library/Audio/Presets/Apple/AUSampler/` (system domain)

AUSampler ships with **no factory preset library** of its own — the plugin exposes the factory-presets property as unsupported (`-10879`). All presets are user-created via AU Lab or programmatically. Instrument content (sample files) must reside under a path containing `/Sounds/`, `/Sampler Files/`, or `/Apple Loops/` for the sampler's path-resolution fallback logic to work.

## Notable parameters

| Parameter ID | Name | Range | Default | Notes |
|---|---|---|---|---|
| 900 (`kAUSamplerParam_Gain`) | Gain | −90 → +12 dB | 0 dB | Global output level |
| 901 (`kAUSamplerParam_CoarseTuning`) | Coarse Tuning | −24 → +24 semitones | 0 | Global pitch shift in semitones |
| 902 (`kAUSamplerParam_FineTuning`) | Fine Tuning | −99 → +99 cents | 0 | Global pitch trim in cents |
| 903 (`kAUSamplerParam_Pan`) | Pan | −1.0 → +1.0 | 0 | Stereo pan |
| 1000–1007 | Performance Parameter 01–08 | −1.0 → +1.0 (or 0–1) | unmapped | User-assignable; can target envelope attack, filter cutoff, LFO rate, etc. per preset design |

Internal subcomponent parameters (filter resonance/cutoff, envelope stages, LFO) are only accessible via `AudioUnitSetProperty` with undocumented property IDs or by mutating the `fullState` plist in memory — they are **not** exposed in the standard AU parameter list.

## Quirks

- **Silent until a sample/instrument is loaded.** The default state produces no sound; a `.aupreset`, SoundFont, DLS2, or EXS24 file must be loaded before any MIDI note triggers audio.
- **No factory presets via standard API.** Querying `kAudioUnitProperty_FactoryPresets` returns error `−10879` (property unsupported). Preset browsing must be done via file-system scanning of `.aupreset` files.
- **Performance Parameters are unmapped by default.** Parameters 1000–1007 control nothing until explicitly mapped inside a preset using AU Lab's Performance Parameter Editor.
- **Loop-point clicks.** Audio files longer than ~2.5 seconds used with loop points can produce audible clicks on playback; loop points must be carefully hand-aligned.
- **Consolidated/monolith sample files bug.** When multiple zones reference different regions within a single concatenated audio file, all zones except the last may output silence at the start of playback (known AVAudioUnitSampler bug).
- **Crash if deallocated before detach.** In AVAudioEngine usage, deallocating the sampler before detaching it from the engine causes an assertion failure (`unbalanced reference count`).
- **Largely undocumented internals.** Apple's official documentation covers only the four top-level parameters; subcomponent control (resonance, envelopes, LFO) requires reverse-engineered property IDs or in-memory plist manipulation.
- **AU Lab dependency for preset authoring.** Due to the complexity of the `.aupreset` plist format, AU Lab (distributed as part of Additional Tools for Xcode) is the practical tool for creating and editing instruments.

## Common recipes

Not applicable — AUSampler is a general-purpose sampler; sound character is entirely determined by the loaded sample content and `.aupreset` design.
