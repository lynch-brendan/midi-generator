---
category: Compression
type: effect
---

# Compression

Dynamics control — glue, punch, tighten, control peaks. Reach for these on "compress," "tighten," "glue," "punchier," "add punch," "control the dynamics," "even it out."

## Options

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
