---
name: DLSMusicDevice
verified: true
last_updated: 2026-09-11
---

# DLSMusicDevice (Apple)

Apple's built-in General MIDI synthesizer. Ships with every macOS. 128 GM
programs + 1 drum kit, all playable via MIDI program change.

## Why this matters

For "realistic instrument by name" requests (trumpet, violin, piano, flute,
oboe, choir, brass, strings, guitar…) DLSMusicDevice is almost always the
right answer. It sounds like the real instrument. Way better than trying to
coax a subtractive synth into a trumpet.

## Preferred alternative: use load_gm_instrument

Nasty already exposes a dedicated `load_gm_instrument(gm_program)` tool that
routes through FluidSynth + the bundled MuseScore SoundFont. That path gives
richer sounds than the OS DLSMusicDevice. **Prefer `load_gm_instrument` over
loading DLSMusicDevice directly.**

## Notable parameters

- Cutoff, Resonance, Attack, Decay, Sustain, Release, Volume.
- Standard AU parameter API — everything exposed.
