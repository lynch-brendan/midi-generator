---
name: AUSampler
verified: false
last_updated: 2026-09-16
preset_paths:
  - "~/Library/Audio/Presets/Apple/AUSampler:aupreset"
---

# AUSampler

Apple's built-in Audio Unit sampler instrument — a lightweight, general-purpose sample playback engine bundled with macOS/iOS that can load .aupreset, DLS, and SoundFont2 (SF2) content.

## Presets on disk

AUSampler uses `.aupreset` files (Apple property list format). <cite index="17-1,17-2">The native instrument format is a standard property list file, but the configuration is quite complex compared to other Audio Units.</cite> User presets are typically saved under `~/Library/Audio/Presets/Apple/AUSampler/`. It can also load:

- **DLS** and **SoundFont2 (.sf2/.dls)** banks — <cite index="4-12,4-13,4-14">AUSampler translates DLS and SoundFont2 preset formats into its own internal format, using an AUSamplerInstrumentData struct where two numbers describe the bank variation and one number the preset.</cite>
- **EXS24** instruments (with caveats) — <cite index="4-9">a directory tree must be created that matches the instrument-specific part of the path where the audio files were located</cite>, and <cite index="14-9,14-10">Logic Pro X extended the EXS24 format with new features (e.g. Audio File Tail) that AUSampler cannot load correctly.</cite>
- GarageBand factory instrument paths live under `/Library/Application Support/GarageBand/Instrument Library/Sampler/Sampler Files/` and <cite index="15-1">GB sampler instruments are under Library/Application Support/GarageBand/Instrument Library/Sampler/Sampler Instruments.</cite>

## Notable parameters

Exposed AudioUnit parameters (from `AudioUnitParameters.h`):

- **Global Gain** — output level of the sampler
- **Coarse Tuning** — semitone tuning offset
- **Fine Tuning** — cents tuning offset
- **Stereo Pan** — output pan

Plus <cite index="1-2,1-3">a set of eight "Performance Parameters" that can each be mapped in AU Lab to modify some aspect of the instrument's state in real time — e.g. Performance Parameter 01 → envelope attack, 02 → filter cutoff, 03 → LFO rate.</cite> Internally, <cite index="7-4,7-5,7-6">the sampler supports modifying subcomponent settings (oscillator pitch, filter cutoff, envelope attack, etc.) via real-time control inputs from the host, and control inputs are "summing" — the effect is the linear sum of all connected inputs.</cite>

## Quirks

- **Silent until a preset is loaded.** A freshly instantiated AUSampler has no sample map and will produce no sound on MIDI input until an `.aupreset`, DLS, or SF2 is loaded.
- **Undocumented/complex preset format.** <cite index="17-7">Due to the complexity of AUSampler's instrument format, it is almost impossible to configure it manually.</cite> Use AU Lab (or Xcode's plist editor) to author presets.
- **Considered an unfinished/"lite" tool.** <cite index="6-15,6-16">Apple hides its full Sampler in GarageBand and Logic Pro but exposes the AUSampler audio unit and its AVAudioUnitSampler wrapper — this appears to be a "Lite" version of their pro Sampler.</cite> Community notes describe it as <cite index="18-6,18-7,18-8">having some fatal flaws and being an apparently unfinished project — using it as a plug-in on the Mac to develop sample-based instruments tends to be frustrating and it can crash the DAW.</cite>
- **Metadata import is unreliable in the plugin GUI.** <cite index="18-9">The AUSampler plug-in GUI is supposed to be able to read SoundFont, DLS and EXS24 metadata files, but in practice rarely does reliably.</cite>
- **May be missing on newer macOS installs.** Users have reported <cite index="13-4">on a new MacBook Air with the latest GarageBand, AUSampler was nowhere to be found under Audio Units → Apple, though it was present on an older 2015 MacBook.</cite>
- **Path fragility on preset load.** <cite index="18-2">After converting an EXS24 or before deploying, sample paths inside the .aupreset usually need to be manually fixed.</cite>
- No factory preset library ships with the plugin itself — presets come from GarageBand/Logic content or user authoring.

## Common recipes

- **General sample playback**: Load a `.sf2` SoundFont (e.g. GM bank) → select preset by bank MSB/LSB + program number → play via MIDI.
- **Multisampled instrument**: Author an `.aupreset` in AU Lab from a folder of key-mapped WAVs, then load in AUSampler.
- **Attack/Release shaping**: Map Performance Parameter 01 → EG1 attack and PP04 → EG1 release, then automate via MIDI CC from the host.
