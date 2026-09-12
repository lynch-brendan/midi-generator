---
category: Vocal
type: instrument
---

# Vocal Sounds

Choir, vocal chops, synth vocal textures. Reach for these on "vocals," "choir," "aahs," "oohs," "vocal chops," "vox," or dreamy vocal-pad requests.

## Options

### GM Choir Aahs (program 52)

- **Character:** synth choir singing "aah"
- **Best for:** cinematic scoring, hip-hop, R&B, dreamy backing vocals
- **Emotional tags:** ethereal, spiritual, dreamy, cinematic
- **How to use:** `load_gm_instrument(channel_id="choir", channel_name="Choir Aahs", gm_program=52)`

### GM Voice Oohs (program 53)

- **Character:** synth voice singing "ooh"
- **Best for:** ambient, dreamy pads, R&B backing, chillwave
- **Emotional tags:** dreamy, romantic, warm, ethereal
- **How to use:** `load_gm_instrument(channel_id="vox", channel_name="Voice Oohs", gm_program=53)`

### GM Synth Voice (program 54)

- **Character:** synthetic vocal-like tone
- **Best for:** electronic, ambient, sci-fi, experimental
- **Emotional tags:** ethereal, alien, dreamy
- **How to use:** `load_gm_instrument(channel_id="vox", channel_name="Synth Voice", gm_program=54)`

### GM Orchestra Hit (program 55)

- **Character:** stab-hit orchestral chord (choir + brass + strings)
- **Best for:** hip-hop stabs, cinematic hits, dramatic accents
- **Emotional tags:** dramatic, punchy, powerful
- **How to use:** `load_gm_instrument(channel_id="hit", channel_name="Orch Hit", gm_program=55)`

### Serato Sample (for vocal chops)

- **Character:** whatever vocal audio is loaded — chopped vocals, one-shots, samples
- **Best for:** hip-hop, house, garage, dubstep — anywhere sampled vocals live
- **Emotional tags:** varies by sample
- **How to use:** Silent until user drags a vocal audio sample into its GUI. Not for AI-driven use. See `plugins/serato-sample.md`.

## Common recipes

- **Cinematic choir bed:** GM Choir Aahs (52) with long note durations, generous reverb (AUMatrixReverb Cathedral).
- **Dreamy R&B vox pad:** GM Voice Oohs (53) with slow chord progression under a lead melody.
- **Hip-hop orch hit:** GM Orchestra Hit (55) on emphasis beats — MIDI 60-72 short staccato notes.

## Comparisons

- **Choir Aahs vs Voice Oohs:** aahs is fuller/brighter; oohs is rounder/warmer.
- **Choir Aahs vs Synth Voice:** choir sounds more natural; synth voice is more alien/synthetic.

## What we're missing

No dedicated vocal synthesizer (Vocaloid, iZotope VocalSynth). No sample library of vocal chops (Splice-style). No formant/vocoder effects. Auto-Tune Pro (see `effects/Pitch.md`) is available for actual mic vocals but doesn't generate vocal tones on its own.
