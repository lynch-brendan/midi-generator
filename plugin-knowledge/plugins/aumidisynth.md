---
name: AUMIDISynth
verified: false
last_updated: 2026-09-16
---

# AUMIDISynth

Apple's built-in General MIDI-compatible AudioUnit synth (`aumu msyn appl`) that plays back SoundFont 2 (.sf2) or DLS bank files — primarily a developer/system component, not a producer-facing instrument.

## Presets on disk

Not applicable — AUMIDISynth has no factory preset library of its own. Its "presets" are the instrument patches contained inside whatever SoundFont 2 (.sf2) or Downloadable Sounds (.dls) bank file the host loads into it via the `kMusicDeviceProperty_SoundBankURL` property. Program-change messages then select patches within that bank.

## Notable parameters

- **Sound Bank URL** (`kMusicDeviceProperty_SoundBankURL`) — path to the .sf2 or .dls file the synth will play from. Without this, the synth has no sounds to produce.
- **MIDI Channel / Program** — GM-compatible, up to 16 multi-timbral channels, patch selected via MIDI program change.
- **Preset Count** — reports the number of patches available in the currently loaded bank.

## Quirks

- **Silent / GM-only until a SoundBank is loaded.** Unlike DLSMusicDevice on macOS (which auto-loads a default GM bank from `/Library/Audio/Sounds/Banks`), AUMIDISynth requires the host to explicitly point it at a .sf2 or .dls file before it will make sound.
- **Developer-oriented component.** AUMIDISynth is exposed as a system AudioUnit primarily for app developers building GM MIDI playback (e.g. via AVAudioEngine / MusicPlayer / MusicSequence). It is not typically instantiated by producers inside DAWs like Logic Pro, which prefer DLSMusicDevice, Sampler, or third-party instruments.
- **Effectively undocumented for end users.** Apple provides no user-facing documentation, preset browser, or editor UI; any UI comes from the host or from third-party wrappers (e.g. "WU: AUMIDISynthesizer").
- **General MIDI character only.** Sound quality and character are entirely determined by the loaded SoundFont, not by the plugin itself — it has no synthesis engine, filters, envelopes, or effects of its own.

## Common recipes (optional)

Not applicable — AUMIDISynth has no inherent sonic character to design recipes around. It is a GM playback engine whose sound is dictated by the user-supplied SoundFont bank.
