---
name: AUSampler
verified: false
last_updated: 2026-10-30
preset_paths:
  - "~/Library/Audio/Presets/Apple/AUSampler:.aupreset"
  - "/Library/Audio/Presets/Apple/AUSampler:.aupreset"
---

# AUSampler

Apple's built-in polyphonic, multi-timbral sampler Audio Unit instrument, available on macOS and iOS, capable of loading .aupreset files, EXS24 instruments, SoundFont (SF2), and DLS2 sound banks.

## Presets on disk

User presets are stored as `.aupreset` files (standard Apple property list format) at:

- `~/Library/Audio/Presets/Apple/AUSampler/` (user presets, created via AU Lab or programmatically)
- `/Library/Audio/Presets/Apple/AUSampler/` (system-wide presets)

GarageBand sampler files (EXS24/sample content) are found under:
- `/Library/Application Support/GarageBand/Instrument Library/Sampler/Sampler Files/`

Note: AUSampler requires a sample/preset to be explicitly loaded before it produces any sound — it ships with no factory preset library of its own.

## Notable parameters

| Parameter | ID | Range | Default | Notes |
|---|---|---|---|---|
| `kAUSamplerParam_Gain` | 900 | -90 → +12 dB | 0 dB | Global output gain |
| `kAUSamplerParam_CoarseTuning` | 901 | -24 → +24 semitones | 0 | Global coarse pitch shift |
| `kAUSamplerParam_FineTuning` | 902 | -100 → +100 cents | 0 | Global fine pitch shift |
| `kAUSamplerParam_Pan` | 903 | -1.0 → +1.0 | 0 | Global stereo pan |
| Performance Parameters 1–8 | 1000–1007 | -1.0 → 1.0 (or 0.0 → 1.0) | unmapped | User-assignable; can modulate oscillator pitch, filter cutoff, envelope attack, etc. Default to "unmapped" state and control nothing until configured. |

## Quirks

- **Silent until a sample is loaded.** AUSampler produces no sound at all until a preset or sample set is explicitly loaded via property APIs, a `.aupreset` file, or a SoundFont/DLS2/EXS24 bank. There is no default patch.
- **Largely undocumented.** Apple's public documentation covers only the four top-level parameters; internal layer/oscillator/filter/envelope properties are largely undocumented and were discussed primarily at WWDC 2011 (Session 411, no longer in Apple's archive).
- **Complex preset format.** The `.aupreset` file is a plist with a deeply nested, complex structure. It is practically impossible to hand-edit; AU Lab (bundled with Additional Tools for Xcode) is the canonical tool for creating and editing presets.
- **Voice count limits.** Concurrent voice playback is capped at 128 on iOS and 256 on macOS. Exceeding this limit causes voices to be silently dropped.
- **File path resolution.** When loading samples, AUSampler uses a cascading path-resolution algorithm looking for `/Sounds/`, `/Sampler Files/`, or `/Apple Loops/` sub-path segments. Samples not in these locations will fail to load on a different machine.
- **Performance Parameters default to unmapped.** The eight assignable Performance Parameters (IDs 1000–1007) do nothing until explicitly configured in AU Lab or via code; an AI automating them before configuration will have no effect.
- **Not a standalone preset browser.** The plugin has no built-in preset browser UI beyond what AU Lab or the host (GarageBand/Logic) exposes.
- **Accessed in GarageBand** via Track → Plugins → AU Instruments → Apple → AUSampler.

## Common recipes

_Because AUSampler is a general-purpose sample playback engine with no built-in sounds, "recipes" depend entirely on loaded content. Below are workflow recipes:_

**Drum kit from WAV files:**
1. In AU Lab, create a new AUSampler instrument.
2. Drag individual one-shot WAV/AIFF files onto the keyboard map, assigning each to a MIDI note range.
3. Set each zone to "One Shot" mode (no looping), velocity-layer as needed.
4. Save as `.aupreset` to `~/Library/Audio/Presets/Apple/AUSampler/`.

**Looped pad from a sample:**
1. Load a sustained texture sample into AU Lab.
2. Enable loop mode on the zone; set loop start/end points.
3. Apply envelope (attack/release) via Performance Parameters if needed.
4. Export preset and load in GarageBand/Logic.

**SoundFont GM bank:**
1. Use `kAUSamplerProperty_LoadPresetFromBank` to load an SF2 or DLS2 file programmatically.
2. Select bank/program number for the desired GM patch.
