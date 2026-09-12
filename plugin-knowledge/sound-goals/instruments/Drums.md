---
category: Drums
type: instrument
---

# Drums

Kicks, snares, hats, claps, percussion, full drum kits. Nasty starts every song with four pre-loaded drum channels — reach for those first.

## Options

### Nasty built-in drum channels (default)

Every fresh Nasty song already has these channels loaded and ready to play:

- **`ch_kick`** — Kick drum. MIDI 36 hits it. Deep foundational thump.
- **`ch_snare`** — Snare. MIDI 38 hits it. Backbeat on 2 and 4 by default.
- **`ch_hh`** — Hi-hat. MIDI 42 = closed, 46 = open. Rhythmic top.
- **`ch_clap`** — Clap. Layers with snare for extra punch on 2 and 4.

- **Character:** clean electronic drum kit — punchy, works for hip-hop, EDM, pop
- **Best for:** any drum-based genre. This is your default.
- **Emotional tags:** varies by pattern — punchy, groovy, driving
- **How to use:** Do NOT create new drum channels. Reference these existing channel_ids in `create_pattern` notes. Typical pop pattern: kick on beats 0 and 2, snare on beats 1 and 3, hats on every 0.5 beat.

### GM Standard Drum Kit (channel 10 / program 128 via load_gm_instrument)

- **Character:** natural acoustic-style GM kit
- **Best for:** rock, jazz, pop when a real-drum feel is wanted
- **Emotional tags:** organic, natural, familiar
- **How to use:** `load_gm_instrument(channel_id="drums", channel_name="Drum Kit", gm_program=128)` — full GM drum map (36=kick, 38=snare, 42=closed hat, 46=open hat, 49=crash, 51=ride, 41-50 various toms/percussion)

### Serato Sample (for chopped drum breaks)

- **Character:** whatever audio sample is loaded — chopped breakbeats, one-shots, drum loops
- **Best for:** hip-hop, jungle, drum & bass, lo-fi (chopping vinyl breaks)
- **Emotional tags:** varies by sample — vintage, gritty, funky
- **How to use:** Silent until user drags an audio sample into its GUI. Do not use for AI-driven drum programming — use the built-in channels instead. See `plugins/serato-sample.md` for details.

## GM drum-map cheatsheet (for load_gm_instrument program 128)

Common hits by MIDI note:
- 35, 36 — kick drum
- 37 — side stick
- 38, 40 — snare
- 39 — hand clap
- 41, 43, 45, 47, 48, 50 — toms (low to high)
- 42 — closed hi-hat
- 44 — pedal hi-hat
- 46 — open hi-hat
- 49 — crash cymbal
- 51, 59 — ride cymbal
- 52 — chinese cymbal
- 53 — ride bell
- 54 — tambourine
- 56 — cowbell
- 60, 61 — bongo (high, low)
- 62, 63, 64 — conga (mute high, open high, low)

## Common patterns

- **Straight pop beat (4/4):** kick on 0 and 2, snare on 1 and 3, closed hats on every 0.5 beat.
- **Trap:** kick on 0 with syncopated hits, snare on 2, hi-hats with rolls (triplet subdivisions).
- **Boom bap:** kick on 0 and half of 2, snare on 1 and 3, swung hi-hats.
- **House:** four-on-the-floor kick (every beat), open hat on the "and" of each beat.

## Comparisons

- **Built-in channels vs GM kit:** built-in channels are punchier and electronic; GM kit is more natural/acoustic.
- **AI-programmed drums vs Serato Sample:** always use built-in channels for AI-programmed drums; Serato Sample only for user-loaded audio.

## What we're missing

No dedicated free drum plugin like MT Power Drum Kit 2 or Sitala yet. No sample library of one-shots (808 packs, snare packs). Bundling those would give producers Splice-tier drum content out of the box.
