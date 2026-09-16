---
category: Keys
type: instrument
---

# Keys

Piano, electric piano, organ, harpsichord — anything with a keyboard voice. Reach for these on any "piano," "keys," "Rhodes," "organ," "e-piano" request.

## Options

### AUSampler

- **Character:** Neutral, transparent sample playback — sound depends entirely on the loaded content (SoundFont/DLS/aupreset). Clean, uncolored digital tone with basic subtractive shaping (filter + envelopes + LFO).
- **Best for:** Loading General MIDI SoundFonts, DLS banks, and custom multisampled instruments for pianos, EPs, organs and other keyed sounds when a lightweight, free, built-in sampler is needed.
- **Emotional tags:** utilitarian, clean, workmanlike, unobtrusive
- **Comparison:** Far less capable and less polished than Kontakt, HALion, or Logic's full Sampler/EXS24; roughly comparable in scope to TX16Wx or the free DecentSampler but with a clunkier workflow and no factory library. A "lite" version of Apple's pro Sampler.
- **How to use:** `load_instrument(channel_id=..., plugin_id="AUSampler", preset_name="<path to .aupreset or .sf2>")` — note the plugin is silent until a preset/soundfont is loaded.

### Vital

- **Character:** Clean and versatile; with third-party lo-fi banks it becomes warm, dusty, and tape-flavored electric-piano-style keys.
- **Best for:** Lo-fi hip-hop keys, synthwave electric pianos, plucky bell tones, hybrid keys layers.
- **Emotional tags:** warm, nostalgic, mellow, chilled, intimate
- **Comparison:** Not a sampled Rhodes/Wurli emulation — more of a synthesized keys sound; pair with a lo-fi preset bank for the vintage keys vibe.
- **How to use:** `load_instrument(channel_id=..., plugin_id="vital", preset_name="<keys preset name>")`

### GM Acoustic Grand Piano (program 0)

- **Character:** clean, natural concert grand piano
- **Best for:** ballads, singer-songwriter, jazz, classical, pop verses
- **Emotional tags:** intimate, sincere, warm, familiar
- **How to use:** `load_gm_instrument(channel_id="piano", channel_name="Piano", gm_program=0)`

### GM Bright Acoustic Piano (program 1)

- **Character:** brighter attack than grand, cuts through a mix
- **Best for:** pop hooks, up-tempo songs, dance tracks needing piano
- **Emotional tags:** cheerful, bright, punchy
- **How to use:** `load_gm_instrument(channel_id="piano", channel_name="Bright Piano", gm_program=1)`

### GM Electric Piano 1 / Rhodes-style (program 4)

- **Character:** classic Rhodes bell tones, warm and mellow
- **Best for:** neo-soul, R&B, jazz, lo-fi hip-hop
- **Emotional tags:** warm, nostalgic, sensual, laid-back
- **How to use:** `load_gm_instrument(channel_id="epiano", channel_name="Rhodes", gm_program=4)`

### GM Electric Piano 2 / DX7-style (program 5)

- **Character:** brighter, glassy FM-style e-piano
- **Best for:** 80s ballads, smooth pop, romantic songs
- **Emotional tags:** dreamy, glossy, romantic, retro
- **How to use:** `load_gm_instrument(channel_id="epiano", channel_name="EP 2", gm_program=5)`

### Dexed E.PIANO 1 patch

- **Character:** authentic DX7 electric piano — the sound of 80s ballads
- **Best for:** anything 80s, adult contemporary, throwback ballads
- **Emotional tags:** nostalgic, glassy, romantic, retro
- **How to use:** `load_instrument(channel_id="dxep", channel_name="DX7 EP", plugin_id="<Dexed id from manifest>", preset_name="E.PIANO 1")`

### GM Harpsichord (program 6)

- **Character:** plucked-string keyboard, baroque, thin and bright
- **Best for:** baroque pastiche, chamber pop, quirky arrangements
- **Emotional tags:** ornate, formal, playful, historical
- **How to use:** `load_gm_instrument(channel_id="harpsi", channel_name="Harpsichord", gm_program=6)`

### GM Clavinet (program 7)

- **Character:** funky electric keyboard, percussive attack
- **Best for:** funk, 70s soul, wah-clav grooves
- **Emotional tags:** funky, groovy, energetic
- **How to use:** `load_gm_instrument(channel_id="clav", channel_name="Clav", gm_program=7)`

### GM Drawbar Organ / Hammond (program 16)

- **Character:** classic Hammond B3 tone
- **Best for:** rock, gospel, blues, soul
- **Emotional tags:** soulful, warm, churchy, powerful
- **How to use:** `load_gm_instrument(channel_id="organ", channel_name="Organ", gm_program=16)`

### GM Church Organ (program 19)

- **Character:** big pipe organ, sacred cathedral sound
- **Best for:** cinematic, dramatic, horror, sacred music
- **Emotional tags:** grand, spiritual, ominous
- **How to use:** `load_gm_instrument(channel_id="organ", channel_name="Church Organ", gm_program=19)`

## Comparisons

- **Acoustic Grand vs Rhodes:** grand is the "real piano" default. Rhodes is warmer, softer, for chill/soul vibes.
- **Rhodes (GM EP1) vs Dexed DX7 EP:** GM Rhodes is quicker; Dexed is more authentic to the actual 80s DX7 sound. Reach for Dexed when the request specifically evokes 80s.
- **Hammond vs Church Organ:** Hammond for rock/gospel; church for cinematic/sacred.

## What we're missing

No dedicated Rhodes/Wurlitzer sample library, no vintage synth key emulations (Prophet, Juno). Adding u-he Podolski or Vitalium in the bundle would help vintage electric-key coverage.
