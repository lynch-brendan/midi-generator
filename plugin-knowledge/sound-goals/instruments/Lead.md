---
category: Lead
type: instrument
---

# Lead Sounds

Front-and-center melodic voices — bright leads, aggressive leads, plucks, arps, synth lead lines. Reach for these on "lead," "melody synth," "arp," "pluck," or specific patch requests like "saw lead" or "supersaw."

## Options

### Odin2

- **Character:** Cutting and expressive; can go from smooth analog leads to aggressive FM/phase-mod screamers with the Ladder or Korg-35 filters biting on top.
- **Best for:** Soaring analog leads, wavetable/vector leads, chiptune leads, FM bell-leads, arpeggiated sequences via the built-in arp.
- **Emotional tags:** soaring, playful, retro, 80s, adventurous
- **Comparison:** More semi-modular and Thor-like than Vital; warmer character than Dexed or Helm; less refined preset library than commercial synths.
- **How to use:** `load_instrument(channel_id=..., plugin_id="Odin2", preset_name="...")`

### TAL-NoiseMaker

- **Character:** Classic analog-style lead — bold, chunky, and expressive; ring mod + sync + FM available for more aggressive/metallic timbres.
- **Best for:** Retro/synthwave leads, portamento mono leads, chiptune-adjacent sync/ring-mod leads, 80s-style lead lines with chorus and delay.
- **Emotional tags:** Nostalgic, driving, playful, punchy, retro-futuristic.
- **Comparison:** Simpler and more focused than Surge XT or Vital leads; more analog-flavored than u-he Zebra; not as hi-fi as Diva but instantly usable and CPU-light.
- **How to use:** `load_instrument(channel_id=..., plugin_id="tal-noisemaker", preset_name="<lead preset name>")` — note: no built-in mod-wheel vibrato, use MIDI learn or LFO routing.

### Vital

- **Character:** Bright, articulate, high-fidelity. Wavetable morphing gives leads a lot of motion and expression; MPE support enables per-note pitch/timbre.
- **Best for:** EDM/festival leads, future bass supersaw-style leads, plucky arps, expressive MPE lead work, hyperpop.
- **Emotional tags:** uplifting, euphoric, cutting, expressive, modern
- **Comparison:** Comparable to Serum for modern wavetable leads; more visual/animated interface than Massive; more digital and precise than analog-modeled leads like Diva.
- **How to use:** `load_instrument(channel_id=..., plugin_id="vital", preset_name="<lead preset name>")`

### Surge XT — Leads category patches

- **Character:** hybrid subtractive/wavetable/FM — huge range of lead tones
- **Best for:** any synth-lead request — bright saws, plucks, hard leads, mellow leads
- **Emotional tags:** varies wildly by patch — from aggressive to dreamy
- **How to use:** `load_instrument(channel_id="lead", channel_name="Lead", plugin_id="<Surge XT id>", preset_name="<lead patch name>")`. Look for patches under `Patches/Leads/`. Enable mono/legato in Scene mode for singing melodic lines; add portamento for slides between notes.

### Dexed — "SAW EM UP" and other bright FM leads

- **Character:** classic FM lead — bright, harmonic-rich, cutting
- **Best for:** 80s pop leads, cinematic hits, vintage electronic music
- **Emotional tags:** heroic, bright, cutting, retro
- **How to use:** `load_instrument(channel_id="lead", channel_name="FM Lead", plugin_id="<Dexed id>", preset_name="SAW EM UP")`

### GM Lead 1 - Square Wave (program 80)

- **Character:** classic 8-bit square wave lead
- **Best for:** chiptune, retro game music, punchy melodic lines
- **Emotional tags:** nostalgic, playful, retro
- **How to use:** `load_gm_instrument(channel_id="lead", channel_name="Square Lead", gm_program=80)`

### GM Lead 2 - Sawtooth (program 81)

- **Character:** classic saw lead
- **Best for:** trance, EDM, 80s pop, cinematic hits
- **Emotional tags:** driving, energetic, cutting
- **How to use:** `load_gm_instrument(channel_id="lead", channel_name="Saw Lead", gm_program=81)`

### GM Lead 3 - Calliope (program 82)

- **Character:** breathy, hollow lead
- **Best for:** dreamy melodies, ambient, chillwave
- **Emotional tags:** dreamy, wistful, ethereal
- **How to use:** `load_gm_instrument(channel_id="lead", channel_name="Calliope Lead", gm_program=82)`

### GM Lead 5 - Charang (program 84)

- **Character:** guitar-like synth lead
- **Best for:** 80s ballads, funk, R&B
- **Emotional tags:** smooth, warm, expressive
- **How to use:** `load_gm_instrument(channel_id="lead", channel_name="Charang Lead", gm_program=84)`

### GM Lead 7 - Fifths (program 86)

- **Character:** synth lead with parallel fifths
- **Best for:** 80s rock, cinematic hits, dramatic melodies
- **Emotional tags:** epic, dramatic, powerful
- **How to use:** `load_gm_instrument(channel_id="lead", channel_name="Fifths Lead", gm_program=86)`

### GM Lead 8 - Bass+Lead (program 87)

- **Character:** thick synth combining bass and lead layers
- **Best for:** cinematic tension, electronic music, dramatic melodies
- **Emotional tags:** thick, powerful, aggressive
- **How to use:** `load_gm_instrument(channel_id="lead", channel_name="Bass+Lead", gm_program=87)`

## Comparisons

- **Surge XT lead vs Dexed lead:** Surge is more versatile and modern; Dexed nails 80s FM specifically.
- **Square (GM 80) vs Saw (GM 81):** square is hollow/chiptune; saw is full/cutting.
- **Calliope vs Saw:** calliope is dreamy/breathy; saw is driving/energetic.

## Common recipes

- **Trance lead:** GM Saw Lead (81) with long note holds and heavy delay/reverb.
- **80s pop lead:** Dexed "SAW EM UP" played in mid-high MIDI range (72-84).
- **Video game lead:** GM Square Lead (80) with short staccato notes.

## What we're missing

No supersaw dedicated patches (Serum-style), no vintage analog leads (Prophet, Juno). u-he Podolski or TAL-NoiseMaker in the bundle would add classic virtual analog lead coverage.
