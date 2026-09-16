---
category: Compression
type: effect
---

# Compression

Dynamics control — glue, punch, tighten, control peaks. Reach for these on "compress," "tighten," "glue," "punchier," "add punch," "control the dynamics," "even it out."

## Options

### AUMultibandCompressor

- **Character:** Clean, transparent, utilitarian — a four-band compressor with no analog-style coloration. Neutral tone shaping via per-band dynamics.
- **Best for:** Corrective multiband dynamics — taming a boomy low end, controlling harsh mids, de-essing/smoothing highs, and light bus/master glue when a transparent tool is preferred over a colored one.
- **Emotional tags:** controlled, tight, clean, balanced, transparent
- **Comparison:** Much more transparent and less characterful than FabFilter Pro-MB, Waves C6, or iZotope Ozone Dynamics; lacks their modern UI, dynamic-phase modes, and sidechain flexibility. Comparable in intent to Logic's Multipressor (same Apple lineage) but with a generic host UI and fewer visualization aids.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUMultibandCompressor", preset_name="...")`

### AUPeakLimiter

- **Character:** Clean, transparent, utilitarian — a no-frills peak limiter with no built-in coloration. Sounds neutral when used lightly; gets pumpy/squashed if pushed hard with Pre-Gain.
- **Best for:** Catching stray peaks on a bus, preventing digital clipping, and modest loudness maximization on rough mixes or voice/podcast material. Good "free safety limiter" at the end of a chain on macOS.
- **Emotional tags:** neutral, safe, clean, unobtrusive
- **Comparison:** Far simpler than mastering limiters like FabFilter Pro-L 2, Waves L2, or Ozone Maximizer — no true-peak, no lookahead control, no output ceiling. More basic than Logic's built-in Adaptive Limiter. Comparable in scope to a bare-bones brick-wall utility; use it when you need a lightweight safety limiter rather than a loudness/character tool.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUPeakLimiter")` then set `PreGain` (dB), `AttackTime` (s), `DecayTime` (s). Note: the output ceiling is fixed at 0 dBFS — follow with a gain plugin if a lower ceiling is required.

### AUDynamicsProcessor (Apple, ships with macOS)

- **Character:** transparent compressor / expander
- **Best for:** general-purpose compression — glue on drums/master, evening out bass, controlling vocal dynamics
- **Emotional tags:** clean, controlled, professional
- **Presets:** Default, Slow Comp, Fast Comp, and others
- **How to use:** `add_plugin_effect(channel_id="<target>", plugin_id="<AUDynamicsProcessor id>", preset_name="<preset>")`. Parameters: Threshold, Head Room, Expansion Ratio/Threshold, Attack Time, Release Time, Master Gain.
- **Detail sheet:** `plugins/audynamicsprocessor.md`

## Common recipes

- **Drum bus glue:** AUDynamicsProcessor with Threshold -12dB, low ratio (~2:1), medium attack, fast release.
- **Aggressive bass compression:** Threshold -18dB, higher ratio (4:1), fast attack.
- **Vocal leveling:** Threshold -15dB, medium ratio (~3:1), medium attack, medium release.

## Comparisons

Only one compressor currently installed. When we add more (TDR Kotelnikov, Klanghelm MJUC jr) this section fills out with color-vs-clean tradeoffs.

## What we're missing

No FET-style aggressive compressor (1176/Klanghelm MJUC jr). No opto/vari-mu warm compressor (LA-2A). No modern SSL-style buss compressor (TDR Kotelnikov). Adding those free plugins would give the AI real character choice for compression.
