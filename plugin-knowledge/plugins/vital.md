---
name: Vital
verified: false
last_updated: 2026-09-13
preset_paths:
  - "~/Music/Vital:.vital"
  - "~/Music/Vital:.vitalbank"
  - "~/Documents/Vital/User/Presets:.vital"
---

# Vital

Free spectral-warping wavetable synthesizer by Matt Tytel, often compared to Serum, with a visual drag-and-drop modulation workflow.

## Presets on disk

Vital uses `.vital` (single preset) and `.vitalbank` (bank) files. Banks are imported via the hamburger menu → "Import Bank". Default user preset locations:

- **macOS:** `~/Music/Vital/User/Presets` (factory content also lives under `/Library/Audio/Presets/Vital` in some install layouts)
- **Windows:** `C:\Users\<user>\Documents\Vital\User\Presets`
- **Linux:** `~/.local/share/vial` (varies)

Custom preset folders must contain a subfolder literally named `Presets` for Vital to index them.

## Notable parameters

- **Oscillator 1/2/3** — up to 3 wavetable oscillators with frequency warping, wave warping, and text-to-wave / drawable wavetables
- **Unison Voices / Detune** — heavily optimized unison; safe to crank voices without huge CPU cost
- **Filter 1 / Filter 2** — multiple filter types (analog, digital, comb, formant, phaser)
- **Sample** — sample-playback oscillator with noise/sample source
- **Macros (1–4)** — four assignable macros for performance control
- **LFOs / DAHDSR Envelopes** — 3 DAHDSR envelopes plus multiple LFOs with custom drawable shapes and stereo split delay
- **FX rack** — Chorus, Compressor, Delay, Distortion, EQ, Filter, Flanger, Phaser, Reverb

## Quirks

- Modulation is assigned by **dragging a source onto a destination knob**; there is a live preview of the modulated value before you drop.
- Vital has an **LFO stereo-split** feature — the left channel's modulation can be delayed relative to the right for wide stereo motion. This is unusual and easy to miss.
- Free/Plus/Pro editions share the same synth engine — **any patch made in Pro will load in the free version identically**; only the factory preset/wavetable library size differs.
- Vital will not index a custom preset folder unless the presets sit inside a subfolder literally named `Presets`.
- Loading a `.vitalbank` also imports its bundled wavetables, samples, and custom LFO shapes.
- Supports MPE and microtonal (`.tun`, `.scl`, `.kbd`) files.
- Only 64-bit DAWs are supported.

## Common recipes (optional)

- **Modern dubstep/reese bass:** Osc 1 saw wavetable, high unison (7–16 voices), moderate detune, Osc 2 with wave warp for movement, LFO → wavetable position, filter 1 in analog LP with envelope mod.
- **Wide evolving pad:** Two oscillators on different wavetables, slow LFO with stereo-split delay → wavetable position, long attack/release envelope, onboard reverb + chorus.
- **Pluck lead:** Single-cycle wavetable, short DAHDSR envelope → amp and filter cutoff, small unison (3 voices), delay + reverb from FX rack.
