# Nasty personal defaults

**Read this BEFORE picking any instrument for a user request.** When the user asks for a sound, route by the specific adjective they used (e.g. "synth bass" vs "upright bass"), not by the general category. Each table below maps a *trigger phrase* to the plugin + preset to reach for.

Plugin names below are what the user has installed. Look them up in the `Installed plugins` manifest to get the actual `plugin_id`. If a preferred plugin is missing from the manifest, fall back to the next entry in the same row's "if missing" note, or to the general-purpose GM entry.

Preset names use fuzzy substring match. If the exact preset name isn't in the plugin's `presets` array, omit `preset_name` and the default program loads.

## Bass

| Trigger words | Plugin | Preset | If plugin missing |
|---|---|---|---|
| "sub", "808", "deep bass", "trap bass" | **Dexed** | `RUMBLE 1` | GM 39 Synth Bass 2 |
| "synth bass", "warm analog bass", "chunky bass" | **TAL-NoiseMaker** | (any bass preset) | GM 38 Synth Bass 1 |
| "growl", "reese", "wobble", "dubstep bass", "neuro" | **Vital** | (any bass/growl preset) | **Surge XT** any bass patch |
| "acid", "gritty bass", "resonant bass" | **Odin2** | (any acid preset) | **TAL-NoiseMaker** |
| "pluck bass", "FM bass", "80s bass" | **Dexed** | `BASS 1` | GM 38 Synth Bass 1 |
| "upright", "jazz bass", "acoustic bass" | GM 32 Acoustic Bass | — | — |
| "electric bass", "rock bass", "pop bass" | GM 33 Fingered Bass | — | — |
| "slap", "funk bass" | GM 36 Slap Bass | — | — |
| "fretless", "smooth bass" | GM 35 Fretless Bass | — | — |
| plain "bass" (no adjective) | **Dexed** | `RUMBLE 1` | GM 39 Synth Bass 2 |

## Chords / Keys / Piano

| Trigger words | Plugin | Preset | If plugin missing |
|---|---|---|---|
| "piano", "grand", plain "chords" | GM 0 Grand Piano | — | — |
| "bright piano", "pop piano" | GM 1 Bright Piano | — | — |
| "Rhodes", "e-piano", "chill keys", "lofi keys" | GM 4 Electric Piano 1 | — | — |
| "80s ballad keys", "glossy EP", "DX7 EP" | **Dexed** | `E.PIANO 1` | GM 5 Electric Piano 2 |
| "Hammond", "organ", "gospel organ" | GM 16 Drawbar Organ | — | — |
| "church organ", "cathedral organ", "pipe organ" | GM 19 Church Organ | — | — |
| "harpsichord" | GM 6 Harpsichord | — | — |
| "clav", "clavinet", "funk keys" | GM 7 Clavinet | — | — |
| plain "keys" | GM 4 Rhodes | — | — |

## Lead

| Trigger words | Plugin | Preset | If plugin missing |
|---|---|---|---|
| "supersaw", "trance lead", "EDM lead", "festival lead" | **Vital** | (any supersaw preset) | GM 81 Saw Lead |
| "cutting saw lead", "80s saw" | GM 81 Saw Lead | — | — |
| "pluck lead", "plucky" | **Vital** | (any pluck preset) | **Surge XT** any pluck patch |
| "FM lead", "80s lead", "cinematic hit" | **Dexed** | `SAW EM UP` | GM 81 Saw Lead |
| "square lead", "chiptune", "8-bit lead" | GM 80 Square Lead | — | — |
| "arp", "arpeggiator", "sequenced lead" | **Odin2** (built-in arp) | — | **Surge XT** |
| "acid lead", "gritty lead", "resonant lead" | **Odin2** | — | **TAL-NoiseMaker** |
| "analog lead", "synthwave lead", "retro lead" | **TAL-NoiseMaker** | — | **Odin2** |
| plain "lead" | **Vital** | (any lead preset) | GM 81 Saw Lead |

## Pad

| Trigger words | Plugin | Preset | If plugin missing |
|---|---|---|---|
| plain "pad", "warm pad", "chord bed" | **Vital** | (any warm pad preset) | GM 89 Warm Pad |
| "cinematic pad", "epic pad", "big pad" | **Surge XT** | (any Pads patch) | GM 48 Strings |
| "ambient", "drone", "atmosphere" | **Odin2** | — | **Surge XT** |
| "synthwave pad", "80s pad", "retro pad" | **TAL-NoiseMaker** | — | GM 90 Poly Pad |
| "choir pad", "aahs", "vocal pad" | GM 91 Choir Pad | — | — |
| "string pad", "orchestral bed", "strings pad" | GM 48 String Ensemble | — | — |
| "shimmer", "ethereal", "halo" | GM 94 Halo Pad | — | — |
| "dark pad", "tense pad", "sci-fi pad", "metallic pad" | GM 93 Metallic Pad | — | — |

## Drums

**Rule: never `create_channel` for drums.** Every Nasty song ships with pre-loaded drum channels — `ch_kick`, `ch_snare`, `ch_hh`, `ch_clap`. Reference these existing channel_ids in `create_pattern` notes. Kit selection (TR-808 for trap, MPC60 for boom-bap, LinnDrum for 80s, etc.) is coming in a future step — for now the built-in electronic kit is what plays.

Exception: if the user explicitly asks for "acoustic drums" / "real drums" / "jazz kit" / "rock kit," reach for `load_gm_instrument(channel_id="drums", channel_name="Drum Kit", gm_program=128)` and use GM's drum map (see `sound-goals/instruments/Drums.md`).

## Vocals — synth sounds (melodic use)

| Trigger words | Plugin | Preset |
|---|---|---|
| "choir", "aahs", "cinematic voices" | GM 52 Choir Aahs | — |
| "oohs", "dreamy vox" | GM 53 Voice Oohs | — |
| "synth voice", "vocoder-ish vox" | GM 54 Synth Voice | — |
| "orch hit", "vocal stab" | GM 55 Orchestra Hit | — |
| "vocal chops" | **Serato Sample** (user drags in) | — |

## "Set me up to record vocals" (mic recording chain)

When the user says "set me up to record vocals" / "let me sing" / "add a vocal channel" / "record a take":

1. `create_channel(id="vocals", name="Vocals", instrument="drums")` — sample-based channel (mic input flows through the same path as sample playback).
2. `add_plugin_effect(channel_id="vocals", plugin_id="Auto-Tune Pro")` — tuning.
3. `add_plugin_effect(channel_id="vocals", plugin_id="klanghelm-mjuc-jr")` — compressor.
4. `add_plugin_effect(channel_id="vocals", plugin_id="valhalla-supermassive")` — verb (fallback: `tal-reverb-4`).
5. Confirm the channel is armed for input — the user will hit record on the transport when they're ready.

Say something short like *"vocal chain up — Auto-Tune → MJUCjr → Supermassive. Arm the channel and hit record."*

## Strings

| Trigger words | Plugin | Preset |
|---|---|---|
| "violin" | GM 40 Violin | — |
| "viola" | GM 41 Viola | — |
| "cello" | GM 42 Cello | — |
| "strings", "ensemble", "orchestral strings" | GM 48 String Ensemble | — |
| "pizzicato" | GM 45 Pizzicato Strings | — |
| "harp" | GM 46 Harp | — |
| "cinematic strings" | GM 48 String Ensemble + Cathedral verb | — |

## Textures / FX / Sound Design

| Trigger words | Plugin | Preset |
|---|---|---|
| "riser", "sweep up" | **Vital** | (any riser preset) |
| "impact", "hit", "cinematic hit" | **Odin2** | (any impact preset) |
| "drone", "atmosphere", "ambient bed" | **Odin2** or **Surge XT** | — |
| "noise", "sound design", "weird" | **Odin2** | — |
| "found sound", "field recording" | **AUSampler** (user loads WAV) | — |

## When none of the above matches

Fall back to the standard flow: read the matching sound-goal cheatsheet under `sound-goals/instruments/`, then pick from the user's manifest. This defaults file is a *shortcut*, not a limit.
