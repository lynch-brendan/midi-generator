---
name: AUSampler
verified: false
last_updated: 2026-09-23
preset_paths:
  - "/Library/Audio/Presets/Apple/AUSampler:.aupreset"
  - "~/Library/Audio/Presets/Apple/AUSampler:.aupreset"
  - "~/Library/Audio/Sounds/Banks:.sf2"
  - "~/Library/Audio/Sounds/Banks:.dls"
---

# AUSampler

Apple's built-in Core Audio sampler instrument (AudioUnit), capable of playing back multi-sample instruments from .aupreset, EXS24, SoundFont2 (.sf2), and DLS2 (.dls) files — available on macOS (OS X Lion+) and iOS (5.0+).

## Presets on disk

AUSampler uses `.aupreset` files (plist/XML format) as its native preset format. Presets are stored in:

- `/Library/Audio/Presets/Apple/AUSampler/` — system-level (`.aupreset`)
- `~/Library/Audio/Presets/Apple/AUSampler/` — user-level (`.aupreset`)
- `~/Library/Audio/Sounds/Banks/` — SF2/DLS sound banks (`.sf2`, `.dls`)

There is no bundled factory preset library; content depends on what is installed (Logic Pro EXS24 instruments, GarageBand content, or user-supplied banks).

## Notable parameters

Only four parameters are formally exposed via the standard AudioUnit parameter API (global scope):

- **Global Gain** — master output level of the sampler
- **Coarse Tuning** — global pitch offset in semitones
- **Fine Tuning** — global pitch offset in cents
- **Stereo Pan** — global stereo panning

Additionally, eight **Performance Parameters** (Performance Parameter 1–8) are available. These default to an unmapped state (controlling nothing) until configured in a preset via AU Lab, where they can be assigned to any internal subcomponent target (e.g., filter cutoff, envelope attack, LFO rate). Once mapped, they are stored in the .aupreset file and are automatable via Parameter Events.

Many deeper properties (voice count, filter resonance, etc.) are undocumented and only accessible via private/hidden property IDs found through reverse engineering.

## Quirks

- **Silent until a sample is loaded**: Produces no sound until a valid instrument is explicitly loaded (.aupreset, .sf2, .dls, EXS24, or individual audio files). There is no default patch.
- **Performance Parameters unmapped by default**: All 8 Performance Parameters control nothing until a preset in AU Lab assigns them to subcomponent targets.
- **Largely undocumented**: Apple's public docs cover only the four global params and eight performance params. Internal controls (e.g., resonance at property ID 4162, voice count at 4104) require reverse engineering to discover.
- **Long audio file clicks**: Audio files longer than ~2.5 seconds can produce audible clicks at loop points — a known reported bug.
- **No voice stealing**: When the voice count limit is reached, new notes are silently ignored rather than triggering voice stealing (confirmed Apple bug FB9835828).
- **Connections partially broken**: MIDI-style Connections for real-time parameter control support only a limited parameter subset, and some listed connections are non-functional.
- **EXS24 compatibility is partial**: Complex Logic Pro X EXS24 presets using newer features may fail or load with reduced functionality; older EXS24 files work reliably.
- **AU Lab required for preset authoring**: Creating .aupreset files with mapped Performance Parameters requires AU Lab, which is no longer bundled with Xcode and must be downloaded separately.
- **Path resolution fallback**: When referenced audio files are missing, AUSampler searches for `/Sounds/`, `/Sampler Files/`, or `/Apple Loops/` path segments and substitutes system directory constants rather than failing cleanly.
- **Not a standard DAW plugin**: AUSampler is primarily a developer-facing Core Audio component. In GarageBand, it is found at Track → Plugins → AU Instruments → Apple → AUSampler, but it requires external tooling to author usable presets.
