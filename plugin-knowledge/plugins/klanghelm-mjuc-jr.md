---
name: MJUCjr
verified: true
last_updated: 2026-09-15
---

# Klanghelm MJUC jr

Free vari-mu (variable-mu tube) compressor from Klanghelm — the stripped-down
"jr" version of the paid MJUC. A mix of MJUC's Mk1 and Mk2 models, emulating
classic 50s/60s broadcast tube compressors. Thick, smooth, gluey, gently
colored — the "make anything sound produced" plugin.

## Notable parameters

- **Compress** — single big knob that dials in gain reduction. More = more
  squash + more tube color from the input stage.
- **Make-Up** — post-comp output gain (-12 dB to +36 dB range).
- **Timing** — 3-way switch: Fast (fast attack/release), Slow (slow
  attack/release), Auto (fast attack, program-dependent release). Also
  affects transformer slew rate and harmonic character.

That's the whole interface. No threshold, no ratio, no attack/release ms.

## Quirks

- Program-dependent envelope — no fixed ms values; the compressor responds
  to signal dynamics, especially in Auto mode.
- Vari-mu style = inherently slow attack, smooth release, always musical —
  it won't grab transients like an 1176.
- The Timing switch changes saturation character, not just envelope times.
- **Missing vs. paid MJUC:** no TIMBRE knob, no separate DRIVE, no HQ mode,
  no auto-gain, no resizable UI, no Mk3 (modern) model, no sidechain.
- Two gain stages + interstage transformer sim baked in — always coloring
  the signal even at low compression.

## Best uses

- Master bus glue (Slow timing, 2-3 dB gain reduction) — the classic use
- Drum bus fatness and thickness (Fast or Auto, push harder)
- Vocals for "old radio" / broadcast warmth
- Bass to tame and thicken simultaneously
- Anything you want to sound "produced" without harsh compression artifacts
- Not for surgical/transparent control — reach for an FET or VCA comp instead
