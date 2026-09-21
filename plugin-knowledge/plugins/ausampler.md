---
name: AUSampler
verified: false
last_updated: 2026-09-21
preset_paths:
  - "/Library/Audio/Presets/Apple/AUSampler:.aupreset"
  - "~/Library/Audio/Presets/Apple/AUSampler:.aupreset"
  - "/Library/Application Support/GarageBand/Instrument Library/Sampler/Sampler Instruments:.exs"
---

# AUSampler

Apple's built-in Core Audio sampler instrument (AudioUnit v2/v3), available on macOS (OS X Lion+) and iOS (5.0+), capable of loading .aupreset, EXS24 (.exs), SoundFont2 (.sf2), and DLS instrument files for MIDI-driven sample playback.

## Presets on disk

AUSampler uses `.aupreset` files (Apple property-list format) as its native preset format. Factory presets for GarageBand instruments live at:

- `/Library/Application Support/GarageBand/Instrument Library/Sampler/Sampler Instruments/` (`.exs`)
- `/Library/Application Support/GarageBand/Instrument Library/Sampler/Sampler Files/` (audio sample files)
- `/Library/Audio/Presets/Apple/AUSampler/` (`.aupreset`)
- `~/Library/Audio/Presets/Apple/AUSampler/` (user presets, `.aupreset`)

Note: AUSampler can also load `.sf2` (SoundFont2) and `.dls` files directly at runtime via `kAUSamplerProperty_LoadInstrument`.

## Notable parameters

Only four parameters are formally exposed via `AudioUnitParameters.h` / `kAudioUnitProperty_ParameterList`:

1. **Global Gain** — master output level of the sampler.
2. **Coarse Tuning** — global pitch offset in semitones.
3. **Fine Tuning** — global pitch offset in cents.
4. **Stereo Pan** — global left/right pan of the sampler output.

Additionally, up to **8 Performance Parameters** (named "Performance Parameter 1" through "Performance Parameter 8" by default) can be mapped via the AU Lab custom view to control internal subcomponents (e.g., envelope attack, filter cutoff, LFO rate) in real time. These are in an "unmapped" state until configured in a preset.

Internal synthesis subcomponents (oscillator pitch, filter cutoff/resonance, DAHDSR envelope stages, LFO rate) can be modulated via MIDI CC connections or via `AudioUnitSetParameter()` on `kAudioUnitScope_Group`. Many of these internal property IDs (e.g., resonance = 4162, voice count = 4104) are undocumented and discoverable only by reverse-engineering.

## Quirks

- **Silent until an instrument is loaded.** AUSampler produces no sound out of the box; it must be given a valid `.aupreset`, `.exs`, `.sf2`, or `.dls` file before it will respond to MIDI.
- **Largely undocumented.** Most internal property IDs and many parameters are not in Apple's public documentation; using them requires reverse-engineering or reliance on community research.
- **Performance Parameters are unmapped by default.** All 8 Performance Parameters do nothing until explicitly mapped to internal subcomponents inside AU Lab or programmatically.
- **EXS24 compatibility is partial.** Logic Pro X–extended EXS24 features (e.g., Audio File Tail) cause load errors or silent failures; only instruments created in Logic Pro 9 or basic Logic Pro X instruments load reliably.
- **Audio files longer than ~2.5 seconds** may produce audible clicks at loop points — a known bug reported in KVR forums.
- **Availability varies by host.** AUSampler has disappeared from GarageBand on some newer macOS versions and may not appear under AU Instruments > Apple in all hosts.
- **AU Lab is required** for designing and exporting `.aupreset` presets interactively; AU Lab is no longer bundled with Xcode and must be downloaded separately from Apple Developer Tools.
- **Absolute sample paths** are baked into `.aupreset` files; the sampler falls back to searching app bundle, Documents, and Library/Sounds directories if the original path is missing.
- **MIDI CC connections** that have no mapping silently do nothing and return no error.

## Common recipes

Not applicable — AUSampler is a general-purpose sample playback engine. Its sound is entirely determined by the loaded instrument file. No synthesis recipes apply independently of a loaded preset.
