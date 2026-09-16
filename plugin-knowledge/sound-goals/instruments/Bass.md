---
category: Bass
type: instrument
---

# Bass Sounds

Anything that lives in the low register — sub bass, growl bass, 808s, funky bass, acid bass, upright bass, electric bass. Reach for these on "bass," "sub," "808," "low end," or genre-specific bass requests.

## Options

### Odin2

- **Character:** Warm, analog-flavored, punchy; capable of earth-shaking low end thanks to Ladder/SEM filter emulations and analog oscillators.
- **Best for:** Classic subtractive bass, growly reese-style bass via unison/detune, FM/phase-mod digital basses, chiptune/8-bit bass.
- **Emotional tags:** gritty, dark, weighty, retro, gnarly
- **Comparison:** Warmer and more analog-voiced than Vital or Surge XT; less polished/preset-driven than Serum; free alternative to Thor-style semi-modular basses.
- **How to use:** `load_instrument(channel_id=..., plugin_id="Odin2", preset_name="...")`

### TAL-NoiseMaker

- **Character:** Chunky, warm, analog-flavored subtractive bass; can go from smooth round sub to filthy, driven, gritty bass with filter drive and bitcrusher.
- **Best for:** Fast, no-nonsense analog bass patches — synthwave sub-bass, old-school house/techno bass, retro game bass, driven acid-style lines using self-resonating LP filter.
- **Emotional tags:** Retro, punchy, warm, nostalgic, filthy, grounded.
- **Comparison:** Warmer and simpler than Serum or Vital; less pristine than Diva but far lighter on CPU; sits in the same territory as Tyrell N6 or a stripped-down Juno-style VA.
- **How to use:** `load_instrument(channel_id=..., plugin_id="tal-noisemaker", preset_name="<bass preset name>")`

### Vital

- **Character:** Clean, modern, digital; can be aggressive and growling with unison + wavetable position modulation, or deep and sub-heavy with a simple sine/triangle table. Very low aliasing and low noise floor.
- **Best for:** Dubstep/riddim growls, reese basses, neuro basses, future bass, house/EDM plucky basses, clean sub layers.
- **Emotional tags:** aggressive, gritty, punchy, futuristic, hard, energetic
- **Comparison:** Sonically in the same league as Serum for wavetable bass design; cleaner and more "digital" than Massive; free, unlike both.
- **How to use:** `load_instrument(channel_id=..., plugin_id="vital", preset_name="<bass preset name>")`

### Surge XT — Basses category patches

- **Character:** hybrid subtractive/wavetable — capable of almost any bass tone
- **Best for:** modern electronic bass, growl bass, wobble bass, synth bass, sub bass
- **Emotional tags:** aggressive, digital, thick, futuristic
- **How to use:** `load_instrument(channel_id="bass", channel_name="Bass", plugin_id="<Surge XT id>", preset_name="<patch name>")`. Patch names live in the plugin's `presets` array and inside `Patches/Basses/`. Common choices: sub-style patches for hip-hop, aggressive growls for DnB/dubstep, warm analog-style basses for lo-fi.

### Dexed — "BASS 1" and other DX7 bass patches

- **Character:** classic FM bass — clicky, digital, plucky
- **Best for:** 80s pop, R&B, funk, anywhere a DX7 bass line fits
- **Emotional tags:** vintage, funky, punchy, retro
- **How to use:** `load_instrument(channel_id="bass", channel_name="FM Bass", plugin_id="<Dexed id>", preset_name="BASS 1")`

### Dexed — "RUMBLE 1"

- **Character:** deep sub-heavy FM bass
- **Best for:** hip-hop, trap, low-end thump under kick
- **Emotional tags:** heavy, dark, foundational
- **How to use:** `load_instrument(channel_id="bass", channel_name="Rumble Bass", plugin_id="<Dexed id>", preset_name="RUMBLE 1")`

### GM Acoustic Bass (program 32)

- **Character:** natural upright bass, jazz-style
- **Best for:** jazz, folk, singer-songwriter, chamber pop
- **Emotional tags:** warm, natural, cool, organic
- **How to use:** `load_gm_instrument(channel_id="bass", channel_name="Upright Bass", gm_program=32)`

### GM Electric Bass Finger (program 33)

- **Character:** classic fingered electric bass
- **Best for:** rock, pop, R&B, funk backing
- **Emotional tags:** grounded, warm, familiar
- **How to use:** `load_gm_instrument(channel_id="bass", channel_name="Electric Bass", gm_program=33)`

### GM Electric Bass Pick (program 34)

- **Character:** picked electric bass, brighter and more articulate
- **Best for:** rock, punk, 80s pop, anywhere pick attack matters
- **Emotional tags:** aggressive, driving, tight
- **How to use:** `load_gm_instrument(channel_id="bass", channel_name="Pick Bass", gm_program=34)`

### GM Fretless Bass (program 35)

- **Character:** smooth, singing electric bass, no fret buzz
- **Best for:** jazz fusion, smooth jazz, sophisticated pop
- **Emotional tags:** smooth, expressive, singing
- **How to use:** `load_gm_instrument(channel_id="bass", channel_name="Fretless Bass", gm_program=35)`

### GM Slap Bass (programs 36-37)

- **Character:** slap-and-pop funk bass
- **Best for:** funk, disco, 80s pop
- **Emotional tags:** funky, groovy, punchy
- **How to use:** `load_gm_instrument(channel_id="bass", channel_name="Slap Bass", gm_program=36)`

### GM Synth Bass 1 (program 38)

- **Character:** classic analog-style synth bass
- **Best for:** disco, 80s pop, retrowave, funk
- **Emotional tags:** retro, warm, punchy
- **How to use:** `load_gm_instrument(channel_id="bass", channel_name="Synth Bass 1", gm_program=38)`

### GM Synth Bass 2 (program 39)

- **Character:** darker, more digital synth bass
- **Best for:** electronic, industrial, dark synthwave
- **Emotional tags:** aggressive, dark, digital
- **How to use:** `load_gm_instrument(channel_id="bass", channel_name="Synth Bass 2", gm_program=39)`

## Comparisons

- **Surge XT bass vs Dexed bass:** Surge is more flexible and modern-sounding; Dexed is authentically 80s FM (clicky/plucky). Reach for Dexed when the vibe calls for DX7 specifically.
- **Upright (GM 32) vs Electric (GM 33-34):** upright for jazz/organic; electric for rock/pop.
- **Synth Bass 1 vs Synth Bass 2:** SB1 is warm and analog; SB2 is darker and more digital.
- **Rumble vs a normal FM bass:** Rumble is sub-heavy for low-end; regular BASS 1 has more mid-attack.

## Common recipes

- **Hip-hop 808:** Dexed RUMBLE 1 at MIDI 24-36 range, hold long notes, layer under a short punchy kick.
- **Wobble bass:** Surge XT bass patch with tempo-synced LFO on filter cutoff (many Surge presets already have this).
- **80s synth bass:** Dexed BASS 1 or GM 38, played at MIDI 36-48.

## What we're missing

No dedicated 808 sub instrument, no acoustic double bass sample library. If bundling more free plugins: Vital or Vitalium would add modern wavetable bass; free 808 SoundFonts would give trap producers a dedicated sub.
