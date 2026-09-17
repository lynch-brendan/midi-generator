---
name: Airwindows Consolidated
verified: false
last_updated: 2026-09-17
---

# Airwindows Consolidated

A free, open-source multi-effect plugin bundling 500+ Airwindows DSP algorithms — reverbs, saturators, tape emulations, EQs, filters, compressors, amp sims, delays, and more — in a single VST3/AU/CLAP/LV2 interface with built-in per-algorithm documentation.

## Presets on disk
Not applicable — no file-based preset library. The plugin does not use file-based presets; DAW project state saves the selected algorithm and its parameter values. There is no factory preset browser.

## Notable parameters
Because Airwindows Consolidated is a meta-plugin that switches between 500+ distinct algorithms, there are **no fixed global parameters**. The parameter set is entirely determined by whichever algorithm is currently selected. Key structural controls present at all times:

- **Algorithm Selector** — drop-down menu (plus jog buttons and typeahead search) at the top of the UI; chooses which Airwindows effect is active. Changing this rewrites all parameter slots.
- **Param 1–10 (algorithm-dependent)** — up to 10 knobs, labelled per the selected algorithm. Each knob shows its name and current value; direct text entry is also available.
- **Collection Filter** — selects the visible subset of algorithms: *Recommended* (greatest hits, default), *Basic* (beginner-friendly), *Recent* (newest additions), or *All Plugins*.
- **Channel Layout** (settings menu) — controls mono/stereo routing, important because many algorithms are inherently stereo.
- **Dark/Light Theme** (settings menu) — follows OS setting or can be overridden.

Notable algorithm families accessible inside the plugin:
- Reverbs: Galactic, Galactic2, CreamCoat, kChamberAR, StarChild2, BrightAmbience3, kAlienSpaceship
- Tape: IronOxide5, TopTape8
- Console/Channel strip: Channel9, TubeDesk, TransDesk, ConsoleX, ConsoleH, ChannelX
- Saturation/Distortion: Spiral2, PurestSaturation, Density
- EQ: SmoothEQ3, Parametric, BiquadStack, AverMatrix
- Amp sims: GrindAmp, FireAmp, LeadAmp, BassAmp, BigAmp
- Delays/Ambience: TapeDelay2, PitchDelay, PurestEcho, ADT
- Bass/Sub: DubSub, FathomFive, Floor, Infrasonic
- Filters: Hermepass, Biquad family, Wolfbot
- Modulation/Chorus: StereoChorus, ChorusEnsemble, Ensemble, Melt
- Lo-fi: DeRez3, DeBez

## Quirks
- **Single-instance, one algorithm at a time** — the plugin runs exactly one algorithm at a time; effects are NOT stackable within one instance. Use multiple instances for chaining.
- **Algorithm switch resets parameter layout** — switching algorithms rewrites all parameter slots. Automation lanes recorded for one algorithm become meaningless if the algorithm is changed; this is a significant AI-automation hazard.
- **Shared plugin ID** — all algorithms share one VST3 plugin ID and one display name ("Airwindows Consolidated") in the DAW. You cannot distinguish two instances by name alone in a mixer view, and batch-replacing a specific algorithm is not possible via the DAW's plugin browser.
- **Parameters are numbered, not named, in DAW automation lanes** — DAW automation sees up to 10 generic parameter slots whose semantic meaning depends on which algorithm is loaded.
- **Sample-rate sensitive** — many algorithms (especially filters) behave differently depending on the project sample rate; center frequencies and character can shift noticeably between 44.1 kHz and 96 kHz.
- **Default algorithm on instantiation** — the plugin opens on the last-used algorithm (or Galactic on first load); there is no "neutral/bypass" default state.
- **No built-in preset save/recall** — users must save/recall via DAW project state or DAW preset slots; there is no internal preset manager.
- **Built-in Airwindopedia** — the right panel displays ~150,000 words of per-algorithm documentation inline; useful for understanding a selected effect but overwhelming for newcomers.
- **Cubase VST3 stability** — some users have reported crashes in Cubase when very large plugin libraries are installed alongside Consolidated (possible VST3 scanner issue, not confirmed fixed).
- **Linux settings file path** — settings are stored at `~/.config/AirwindowsConsolidated` (not `~/AirwindowsConsolidated` as in earlier versions).
- **CPU usage** — generally very light; the entire plugin binary is ~8 MB despite containing 500+ algorithms.

## Common recipes
_Not applicable — Airwindows Consolidated is an effect plugin, not a synthesizer._
