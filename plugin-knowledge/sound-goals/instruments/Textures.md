---
category: Textures
type: instrument
---

# Synth Textures & FX Sounds

Non-melodic sonic material — noise, hits, risers, impacts, drones, ambient beds. Reach for these on "riser," "impact," "hit," "sweep," "atmosphere," "noise," "FX sound."

## Options

### Surge XT — FX and non-melodic patches

- **Character:** hybrid wavetable/FM/subtractive — capable of arbitrary sound-design
- **Best for:** risers, sweeps, impacts, drones, cinematic FX
- **Emotional tags:** varies wildly by patch — tense, alien, cinematic
- **How to use:** `load_instrument(channel_id="fx", channel_name="FX", plugin_id="<Surge XT id>", preset_name="<FX patch name>")`. Look for patches labeled with SFX, FX, Sweep, Riser, Impact, or Drone in `Patches/`. Long notes for drones/pads, short accents for hits.

### Surge XT Effects (as a sound source via wavetables — advanced)

- **Character:** signal-processing chain — technically an effect but with the right patch can generate ambient textures on top of any note trigger.
- **Best for:** unconventional workflows only. Prefer Surge XT synth for texture generation.

### GM FX 1 - Rain (program 96)

- **Character:** rain-like textured noise
- **Best for:** ambient beds, sound design, cinematic weather
- **Emotional tags:** meditative, gentle, atmospheric
- **How to use:** `load_gm_instrument(channel_id="fx", channel_name="Rain FX", gm_program=96)`

### GM FX 2 - Soundtrack (program 97)

- **Character:** cinematic wash / film-score bed
- **Best for:** film scoring, cinematic transitions, atmospheric intros
- **Emotional tags:** cinematic, mysterious, expansive
- **How to use:** `load_gm_instrument(channel_id="fx", channel_name="Soundtrack FX", gm_program=97)`

### GM FX 3 - Crystal (program 98)

- **Character:** shimmering crystalline texture
- **Best for:** ambient, new-age, magical/fantasy scoring
- **Emotional tags:** shimmering, magical, ethereal
- **How to use:** `load_gm_instrument(channel_id="fx", channel_name="Crystal FX", gm_program=98)`

### GM FX 4 - Atmosphere (program 99)

- **Character:** breathy atmospheric wash
- **Best for:** ambient, cinematic intros, tension builds
- **Emotional tags:** atmospheric, tense, expansive
- **How to use:** `load_gm_instrument(channel_id="fx", channel_name="Atmosphere FX", gm_program=99)`

### GM FX 5 - Brightness (program 100)

- **Character:** bright shimmering high-end texture
- **Best for:** magical/fantasy scoring, ambient sparkle, cinematic
- **Emotional tags:** bright, magical, uplifting
- **How to use:** `load_gm_instrument(channel_id="fx", channel_name="Brightness FX", gm_program=100)`

### GM FX 6 - Goblins (program 101)

- **Character:** eerie warbling texture
- **Best for:** horror, sci-fi, tension, dark ambient
- **Emotional tags:** eerie, unsettling, alien
- **How to use:** `load_gm_instrument(channel_id="fx", channel_name="Goblins FX", gm_program=101)`

### GM FX 7 - Echoes (program 102)

- **Character:** echoing metallic texture
- **Best for:** ambient, cinematic space, sci-fi
- **Emotional tags:** vast, echoing, mysterious
- **How to use:** `load_gm_instrument(channel_id="fx", channel_name="Echoes FX", gm_program=102)`

### GM FX 8 - Sci-Fi (program 103)

- **Character:** synthetic sci-fi texture
- **Best for:** sci-fi scoring, electronic music, futuristic
- **Emotional tags:** futuristic, alien, cold
- **How to use:** `load_gm_instrument(channel_id="fx", channel_name="Sci-Fi FX", gm_program=103)`

### GM Gunshot (program 127)

- **Character:** noise-based gunshot hit
- **Best for:** action scoring, hip-hop production, sound design
- **Emotional tags:** aggressive, sudden, dramatic
- **How to use:** `load_gm_instrument(channel_id="fx", channel_name="Gunshot", gm_program=127)`

### Serato Sample (for custom textures)

- **Character:** whatever audio the user loads — noise, samples, field recordings
- **Best for:** sample-based sound design
- **How to use:** Silent until user drops in a sample. Not for AI-driven use.

## Common recipes

- **Cinematic riser:** Surge XT FX riser patch, MIDI 60-84 rising note over 4-8 beats leading into a drop.
- **Atmospheric ambient bed:** GM Atmosphere FX (99) or Soundtrack FX (97), long chord tones with heavy reverb.
- **Impact hit:** GM Orchestra Hit (55) or Gunshot (127) on the "1" of a section change.

## What we're missing

No dedicated sound-design library, no cinematic sample libraries (Cinematique, Heavyocity). No noise/glitch plugin. Ambient/sound-design work is thin here — the Surge XT + GM FX combo covers basics only.
