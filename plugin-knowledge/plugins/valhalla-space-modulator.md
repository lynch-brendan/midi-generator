---
name: ValhallaSpaceModulator
verified: true
last_updated: 2026-09-15
---

# Valhalla Space Modulator

Free retro modulation effect from Valhalla DSP — flangey, chorusy, tape-echoey
space textures with 11 selectable algorithms. Named as an homage to the 80s
Publison DHM 89 B2 harmonizer/modulation processor. Deceptively simple UI, wide
sonic range: through-zero flanging, barberpole rise/fall, detune/doubling, weird
short reverbs, ensemble.

## Modes

11 algorithms selected via the **Mode** menu. Categories (exact labels vary by
version):

- **Flange (Up / Down)** — classic single-delay-line flanger, modulation sweeps
  up or down from the manual setting.
- **TZF (Through-Zero Flanger)** — two delay lines cross at zero, giving the
  symmetrical, tape-splice notch sweep. The "correct" flanger sound.
- **BarberPole (Up / Down)** — pitch-shifted feedback path creates a perpetually
  rising or falling flange that never resolves. Great for tension.
- **Ensemble / 360 Ensemble** — multi-tap chorus with rotating modulation, wide
  Solina/Juno-style wash.
- **Symphonic** — dense multi-voice chorus, thicker than Ensemble.
- **Doubler** — short delay + slow modulation for vocal/instrument thickening.
- **Detune** — pitch-shifted taps, no LFO character, for width without wobble.
- **Chorus** — traditional single-voice chorus tone.

## Notable parameters

- **Mode** — algorithm selector (see above). This is the big lever.
- **Mix** — dry/wet blend. 100% for full-wet flanger/reverb use, ~30–50% for
  chorus/doubler.
- **Manual (Delay Ms)** — center delay time. Sub-5 ms = flange, 5–20 ms =
  chorus, 20–50 ms = doubler, higher = short slap/reverb-ish.
- **Feedback** — resonant emphasis on the flange comb. Bipolar in some modes
  (negative = inverted flange notches). Extreme values self-oscillate.
- **Mod Rate** — LFO speed. Not tempo-syncable.
- **Mod Depth** — LFO amount around the Manual setting.
- No dedicated Width or EQ knobs — stereo width comes from the algorithm
  itself. If you need EQ shaping, place an EQ after it.

## Quirks

- **Not tempo-synced.** Rate is in Hz only; no host-BPM division. For rhythmic
  modulation, automate Rate manually.
- **No presets stored in the plugin manifest.** Valhalla plugins expose presets
  via their own preset menu; the VST3 program list is minimal or empty. Don't
  rely on program-change automation.
- **Self-documenting UI** — hovering any knob shows a tooltip in the bottom-left
  strip. No external manual.
- **High feedback + TZF/BarberPole** can produce howling self-oscillation. Ride
  the Mix or put a limiter after it if experimenting live.
- Mono-in / stereo-out capable; the algorithm generates the stereo image.

## Best uses

- Vocal doubling / thickening (Doubler or Detune, Mix ~30%)
- Ambient guitar chorus/flange (Ensemble, Symphonic, TZF)
- Retro synth wash on pads and Rhodes (360 Ensemble, Chorus)
- Risers and transitions (BarberPole Up/Down, automate Feedback)
- Lofi movement on drum busses (subtle Flange Down, low Depth)
