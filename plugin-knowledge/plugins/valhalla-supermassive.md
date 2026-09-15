---
name: ValhallaSupermassive
verified: true
last_updated: 2026-09-15
---

# Valhalla Supermassive

Free feedback-delay-network reverb/delay from Valhalla DSP. Huge cinematic
tails, ambient pads, shoegaze washes, otherworldly space — the go-to when
you want reverb to become the sound rather than sit behind it.

## Modes

22 modes total, each named after a celestial object. Grouped roughly by
character:

- **Clean shimmer / short-to-medium bloom** — Gemini, Hydra, Lyra,
  Capricorn, Cirrus Major, Cirrus Minor. Fast attack, tighter density.
- **Dense clouds / long ambient tails** — Centaurus, Sagittarius,
  Andromeda, Great Annihilator, Cassiopeia, Orion. Slower attacks,
  very high echo density, drone territory.
- **2022–2023 additions** — Aquarius, Pisces (v2.4), Scorpio, Libra
  (v2.5), Leo, Virgo (v3.0). Extra flavors bridging the clean/dense
  extremes.
- **Sirius (new in v5.0.0, Nov 2025)** — clear-throughout-decay mode.
  Fast attack, smooth decay, unusually powerful Low Cut / High Cut,
  standard-echo behavior. Best mode for modulated delays and for
  reverbs where lows thin out over the tail.

Modes are the "presets" — there is no factory preset browser exposed
through the plugin API.

## Notable parameters

- **Mix** — dry/wet balance.
- **Delay Ms / Delay Note** — length of the longest delay line in the
  FDN. Click "Msec" to toggle to note-sync (syncs to DAW tempo).
- **Feedback** — how long the tail sustains. Values above ~90% approach
  infinite drone/self-oscillation territory.
- **Density** — how much the delays cross-mix. Low = grainy discrete
  echoes, high = smooth continuous wash.
- **Mod Rate / Mod Depth** — LFO on the delay lines. Chorused pads and
  shimmering movement at moderate depth; seasick at max.
- **Warp** — spreads delays out and shortens them. 0% = all delays at
  the Delay length (echoey), >50% = more reverberant/smeared.
- **Width** — stereo spread of the wet signal.
- **EQ Low / High (Low Cut / High Cut)** — tail tone shaping. Sirius
  mode has notably steeper/more useful filters than other modes.

## How to switch modes from chat

Mode is exposed as a **VST3 parameter named "Mode"** (integer index into
the mode list above, roughly in order: 0 = Gemini, 1 = Hydra, etc.).
Use the `set_plugin_param` tool: `{"name": "Mode", "value": <index>}`
on the channel that has Supermassive loaded. No need to open the plugin
GUI. The Mix, Feedback, Density, Delay Ms, etc. are also all
`set_plugin_param`-controllable by name.

## Quirks

- Mode roster grows over versions — code that hard-codes a mode list will
  drift. Newer modes (Sirius, Leo, Virgo, Scorpio, Libra) don't exist in
  older installs. Ask the user or check the plugin's param list before
  guessing an index.
- No standard preset-program API — the Mode param is the only "preset"
  interface. Don't try program change messages.
- Feedback near 100% is genuinely infinite; freezing a tail is a
  performance move, not a mistake.
- CPU is very light for how big it sounds.

## Best uses

- Ambient / shoegaze / dream pop pads (Andromeda, Cassiopeia, high mix)
- Cinematic pre-choruses and drops (feedback 50–70%, high mix, Great
  Annihilator or Sagittarius)
- Vocal throws with note-synced delay + moderate feedback
- Drone beds and sound design (feedback 95%+, freeze the tail)
- Clean tempo-synced modulated delays — Sirius, moderate feedback,
  Mod Depth ~20%
- Send/aux effect on drums for reverse-swell / whoosh transitions
