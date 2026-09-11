---
name: Surge XT
verified: true
last_updated: 2026-09-11
preset_paths:
  - "~/Library/Application Support/Surge XT/patches_factory:fxp"
  - "~/Library/Application Support/Surge XT/patches_3rdparty:fxp"
  - "~/Documents/Surge XT/Patches:fxp"
---

# Surge XT

Free open-source subtractive + wavetable synth by Surge Synth Team. Flagship
free synth for modern producers — huge range from analog-style basses to
wavetable pads.

## Presets on disk

- **macOS factory patches:** `~/Library/Application Support/Surge XT/patches_factory/**/*.fxp`
- **macOS user patches:** `~/Documents/Surge XT/Patches/**/*.fxp`
- **macOS 3rd-party patches:** `~/Library/Application Support/Surge XT/patches_3rdparty/**/*.fxp`
- **Windows factory:** `%LOCALAPPDATA%\Surge XT\patches_factory\**\*.fxp`
- **Windows user:** `%USERPROFILE%\Documents\Surge XT\Patches\**\*.fxp`

Categories are sub-folders: `Basses/`, `Leads/`, `Pads/`, `Keys/`, `Percussion/`, etc.

## Loading a patch

`.fxp` file bytes → VST3 `setStateInformation`. The Nasty engine already knows
how to apply raw state via the `state` field of `load_plugin`; a follow-up
build wires the file → base64 → engine path.

## Notable parameters

- **Macro 1–8** (8 assignable macros per scene). Assignments are patch-specific.
- Common pattern: Macro 1 = filter cutoff, Macro 2 = resonance, Macro 3 = amp
  attack, but always patch-specific.
- **A Filter 1 Cutoff / Resonance** — global filter, exposed always.
- **Scene A / Scene B** — two independent voice engines. Use Scene A for
  simple patches.

## Quirks

- Default patch on instantiation is `Init` — silent-ish until you pick or
  load a real patch.
- Wavetable oscillators load samples on demand — first note after a patch
  change may lag briefly.
