---
category: Strings
type: instrument
---

# Strings

Bowed and plucked string family. Reach for these when the user asks for violin, viola, cello, bass, string ensemble, or any orchestral string voicing.

## Options

### GM Violin (via load_gm_instrument, program 40)

- **Character:** natural, singing, agile top-line strings
- **Best for:** melodic leads, ballad top lines, folk hooks
- **Emotional tags:** yearning, intimate, romantic, cinematic
- **How to use:** `load_gm_instrument(channel_id="violin", channel_name="Violin", gm_program=40)`

### GM Viola (program 41)

- **Character:** warm midrange, darker than violin, slightly nasal
- **Best for:** inner voice in string arrangements, moody solo lines
- **Emotional tags:** melancholic, introspective, warm
- **How to use:** `load_gm_instrument(channel_id="viola", channel_name="Viola", gm_program=41)`

### GM Cello (program 42)

- **Character:** rich lower-midrange, human vocal quality
- **Best for:** melody in ballads, warm counter-melody under vocals
- **Emotional tags:** mournful, warm, dignified, heavy-hearted
- **How to use:** `load_gm_instrument(channel_id="cello", channel_name="Cello", gm_program=42)`

### GM Contrabass (program 43)

- **Character:** deep, foundational, orchestral low end
- **Best for:** orchestral bass roots, cinematic tension holds
- **Emotional tags:** grave, cinematic, weighty
- **How to use:** `load_gm_instrument(channel_id="contrabass", channel_name="Contrabass", gm_program=43)`

### GM String Ensemble (program 48)

- **Character:** wide, blended, cinematic string section
- **Best for:** pads that sound like an orchestra, cinematic swells, huge chord beds
- **Emotional tags:** epic, cinematic, uplifting, sweeping
- **How to use:** `load_gm_instrument(channel_id="strings", channel_name="Strings", gm_program=48)`

### GM Pizzicato Strings (program 45)

- **Character:** short plucked strings, staccato, percussive
- **Best for:** rhythmic bass lines, playful counter-melodies, movie-score tension builds
- **Emotional tags:** playful, mischievous, tense, nimble
- **How to use:** `load_gm_instrument(channel_id="pizz", channel_name="Pizzicato", gm_program=45)`

### GM Tremolo Strings (program 44)

- **Character:** sustained bowed strings with rapid tremolo texture
- **Best for:** suspense, horror scoring, tension builds
- **Emotional tags:** tense, uneasy, urgent, cinematic
- **How to use:** `load_gm_instrument(channel_id="tremolo", channel_name="Tremolo Strings", gm_program=44)`

### GM Orchestral Harp (program 46)

- **Character:** shimmering plucked strings, ethereal
- **Best for:** glissandos, delicate arpeggios, dreamy intros
- **Emotional tags:** dreamy, angelic, delicate, ethereal
- **How to use:** `load_gm_instrument(channel_id="harp", channel_name="Harp", gm_program=46)`

## Comparisons

- **Violin vs Viola:** viola is warmer and one fifth lower — use viola when you want strings but "not the obvious top line."
- **Cello vs Contrabass:** cello is melodic-range, contrabass is bass-range. Cello for singing lines; contrabass for foundational roots.
- **String Ensemble vs individual:** ensemble = cinematic pad. Individual = solo voice with personality.

## What we're missing

No dedicated orchestral sample library (VSCO, Spitfire, etc.). Everything here is via the bundled MuseScore SoundFont — good enough for demos and pop production, not for scoring films.
