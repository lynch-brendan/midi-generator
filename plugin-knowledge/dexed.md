---
name: Dexed
verified: true
last_updated: 2026-09-11
---

# Dexed

Free open-source 6-operator FM synth by Digital Suburban. Emulates the
classic Yamaha DX7. Great for punchy FM basses, bells, e-pianos, and
classic 80s synth textures.

## Presets

Unlike most modern synths, Dexed **fully exposes its factory cartridge
through the standard VST3 program API** — so the plugin's `presets`
array in the manifest is authoritative. No file-system scanning needed.

Currently loaded cartridge is a 32-patch bank; typical names include
"SAW EM UP", "RUMBLE 1", "CASCADE 21", "E.PIANO 1", "BASS 1", etc.

## Loading .syx cartridges (advanced)

Dexed can load additional DX7 SysEx cartridges (`.syx` files, 4104 bytes).
Not needed for MVP — the default cartridge already covers a lot.

## Notable parameters

- **Algorithm** (1–32) — the FM operator routing. Cartridge patches set
  this per program.
- **Cutoff / Resonance** — the built-in filter stage.
- **6 operator envelopes** exposed as EG params.

## Quirks

None — this is one of the cleanest plugins from an automation-friendliness
perspective. All 32 patches, all params, all preset selection via standard
API.
