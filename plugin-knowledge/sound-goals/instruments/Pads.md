---
category: Pads
type: instrument
---

# Pads & Atmospheres

Sustained background textures — warm pads, ethereal pads, evolving atmospheres, drones. Reach for these on "pad," "atmosphere," "background," "wash," "drone," or genre requests like "ambient" or "cinematic bed."

## Options

### Surge XT — Pads category patches

- **Character:** hybrid subtractive/wavetable — capable of warm, ethereal, evolving, aggressive pad textures
- **Best for:** any pad request. Long attack, long release, layered scenes.
- **Emotional tags:** varies by patch — dreamy, tense, uplifting, ethereal
- **How to use:** `load_instrument(channel_id="pad", channel_name="Pad", plugin_id="<Surge XT id>", preset_name="<pad patch name>")`. Look under `Patches/Pads/`. Long Amp EG Attack/Release + Scene B engaged for detuned layering gives the biggest pad sound.

### GM Pad 1 - New Age (program 88)

- **Character:** shimmering, atmospheric, bell-tinged pad
- **Best for:** ambient, chillout, cinematic beds
- **Emotional tags:** ethereal, dreamy, spacious
- **How to use:** `load_gm_instrument(channel_id="pad", channel_name="New Age Pad", gm_program=88)`

### GM Pad 2 - Warm (program 89)

- **Character:** warm string-like pad
- **Best for:** ballads, R&B, cinematic warmth
- **Emotional tags:** warm, comforting, nostalgic
- **How to use:** `load_gm_instrument(channel_id="pad", channel_name="Warm Pad", gm_program=89)`

### GM Pad 3 - Polysynth (program 90)

- **Character:** classic polysynth pad, moderate brightness
- **Best for:** 80s pop, synthwave, retrowave
- **Emotional tags:** retro, dreamy, glossy
- **How to use:** `load_gm_instrument(channel_id="pad", channel_name="Poly Pad", gm_program=90)`

### GM Pad 4 - Choir (program 91)

- **Character:** synth choir pad
- **Best for:** cinematic tension, dramatic scoring, ambient
- **Emotional tags:** ethereal, spiritual, cinematic
- **How to use:** `load_gm_instrument(channel_id="pad", channel_name="Choir Pad", gm_program=91)`

### GM Pad 5 - Bowed (program 92)

- **Character:** bowed-glass texture, ethereal
- **Best for:** ambient, atmospheric intros, cinematic
- **Emotional tags:** dreamy, ghostly, delicate
- **How to use:** `load_gm_instrument(channel_id="pad", channel_name="Bowed Pad", gm_program=92)`

### GM Pad 6 - Metallic (program 93)

- **Character:** metallic-textured pad, brighter and colder
- **Best for:** sci-fi, cinematic tension, industrial
- **Emotional tags:** cold, futuristic, tense
- **How to use:** `load_gm_instrument(channel_id="pad", channel_name="Metallic Pad", gm_program=93)`

### GM Pad 7 - Halo (program 94)

- **Character:** angelic, shimmering pad with high harmonics
- **Best for:** ambient, spiritual scoring, cinematic
- **Emotional tags:** angelic, ethereal, uplifting
- **How to use:** `load_gm_instrument(channel_id="pad", channel_name="Halo Pad", gm_program=94)`

### GM Pad 8 - Sweep (program 95)

- **Character:** evolving pad with slow filter sweep
- **Best for:** transitions, cinematic builds, atmospheric intros
- **Emotional tags:** evolving, tense, cinematic
- **How to use:** `load_gm_instrument(channel_id="pad", channel_name="Sweep Pad", gm_program=95)`

### GM String Ensemble (program 48)

- **Character:** cinematic orchestral strings — works as an epic pad
- **Best for:** cinematic chord beds, epic ballads, huge choruses
- **Emotional tags:** epic, cinematic, uplifting
- **How to use:** `load_gm_instrument(channel_id="pad", channel_name="Strings Pad", gm_program=48)`

## Comparisons

- **Surge XT pad vs GM pads:** Surge is way more designed and interesting; GM pads are basic but reliable. Use Surge when the vibe is particular; GM when you just need a chord bed.
- **Warm Pad (GM 89) vs Poly Pad (GM 90):** warm is softer and darker; poly is more classically 80s-synth.
- **Halo Pad (GM 94) vs Choir Pad (GM 91):** halo is instrumental-shimmering; choir is voice-like.

## Common recipes

- **Dreamy chill pad:** GM Warm Pad (89) at 2-4 beat note holds, add generous reverb (AUMatrixReverb Cathedral preset).
- **Cinematic tension bed:** GM Metallic Pad (93) or Sweep Pad (95) with slow chord changes.
- **Epic ballad bed:** GM String Ensemble (48) or Surge XT big pad, chord progression with long note durations.

## What we're missing

No dedicated wavetable/granular pad tools (Serum, Omnisphere). Adding Vitalium in the bundle would open modern evolving pad territory.
