---
name: Surge XT Effects
verified: false
last_updated: 2026-09-11
---

# Surge XT Effects

Standalone effects-plugin version of the Surge XT synthesizer's FX section, exposing Surge's full effect suite (reverbs, delays, distortion, vocoder, Airwindows, etc.) as a VST3/AU insert.

## Presets on disk

Not applicable — this plugin exposes presets via the standard VST/AU program API. The plugin hasn't implemented file-based preset loading, but you can use RestoreState() of files saved by the standalone Surge XT Effects app.

## Notable parameters

Parameters are generically named ("FX Type", "FX Parameter *"), so per-parameter automation by name is of limited use. The meaningful controls are:

- **FX Type** — selects which Surge effect algorithm is loaded (reverb, delay, chorus, vocoder, Airwindows, etc.)
- **FX Parameter 1..N** — generic slots whose meaning depends entirely on the currently selected FX Type
- **Tempo-sync switches** — switches allow tempo sync for appropriate parameters (e.g. delay time, LFO rate)
- Sidechain-related parameters (relevant when FX Type = Vocoder)

## Quirks

- **Generic parameter names.** The host sees `FX Type` + numbered `FX Parameter` slots rather than named controls; the real semantics only exist inside the plugin GUI once an FX Type is chosen. Any automation script must know the current FX Type to interpret slots.
- **Sidechain input is optional but sometimes required.** The plugin has an optional Side Chain input that may be required by some effects (cf Vocoder).
- **Vocoder is the headline use case.** With the Surge Effects Bank plugin, you can sidechain a modulator in while also using the current track as a carrier source, allowing other synths or audio sources into the vocoder circuit — something the main Surge XT synth cannot do.
- **Preset loading via host state, not files.** Plugin hasn't implemented preset loading to date; you can, however, use RestoreState() of files saved by the standalone Surge XT Effects app. Don't expect a scannable user-preset folder.
- **Shipped as an extra plugin, not a separate download.** The Surge Effects Bank plugin is included as an extra plugin in the macOS and Windows Surge installers.
- **Airwindows sub-selector.** When FX Type is Airwindows, the Airwindows Type parameter is streamed/unstreamed as its own integer parameter — changing it swaps the meaning of the FX Parameter slots again.
- Distinct from the Surge XT synth plugin; installs as its own VST3/AU (often labeled "Surge XT Effects" or "Surge Effects Bank").
