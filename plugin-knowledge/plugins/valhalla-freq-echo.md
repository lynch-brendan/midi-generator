---
name: ValhallaFreqEcho
verified: true
last_updated: 2026-09-15
---

# Valhalla Freq Echo

Free Bode-style frequency-shifting delay from Valhalla DSP. Every repeat
gets shifted in Hz (not semitones), so echoes drift inharmonically —
great for dubby, wobbly, ethereal, self-oscillating textures.

## Notable parameters

- **Mix** — dry/wet.
- **Delay Ms** — echo time. Free-running, roughly 1 ms to ~1 second. No
  tempo sync, no zipper noise on automation.
- **Feedback** — repeats. Near max = self-oscillation even with no input,
  producing sustained drones.
- **Shift Hz** — Bode frequency shift applied to the wet signal each pass
  through the feedback loop. Bipolar: positive = upward Hz drift per
  repeat, negative = downward. Near 0 Hz = subtle chorus/phasing.
- **Feedback Filter** — a single tilt-style cut in the feedback path.
  Darkens repeats (dub) or keeps them bright/metallic.

## Quirks

- Frequency shift is not pitch shift. Adding a constant Hz value breaks
  harmonic ratios, so shifted repeats sound detuned and inharmonic. That
  dissonance is the sound — don't fight it.
- No tempo sync. Set Delay Ms by ear.
- No preset browser and no factory presets. Dial in by hand.
- No Run/Reverse control — that's a different Valhalla plugin. Freq Echo
  is Mix / Delay Ms / Feedback / Shift Hz / Feedback Filter, period.
- CPU-light. Cheap to stack multiple instances.

## Best uses

- Dubby delays that slowly rise or fall in pitch
- Ambient soundscapes and evolving pads
- Barberpole flanging/phasing at very small Shift Hz values (±0.1 to ±2 Hz)
- Weirding up drums, vocals, or guitars
- Self-oscillating drones (Feedback near max, tweak Shift Hz for motion)
- Reverse-echo feels via Mix automation on a send
