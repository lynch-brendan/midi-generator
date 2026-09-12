---
category: Filters
type: effect
---

# Filters

Low-pass, high-pass, band-pass filtering — carve frequencies, do filter sweeps, telephone/radio effects. Reach for these on "filter," "low-pass," "high-pass," "sweep," "telephone effect," "radio effect," "muted," "underwater."

## Options

### AUBandpass (Apple, ships with macOS)

- **Character:** narrow bandpass filter, isolates a frequency band
- **Best for:** telephone/radio effects, feedback removal at a specific frequency, creative filter sweeps
- **Emotional tags:** filtered, radio-like, telephonic, distant, dreamy
- **How to use:** `add_plugin_effect(channel_id="<target>", plugin_id="<AUBandpass id>")`. Parameters: CenterFrequency (20 Hz - Nyquist/2, default 5000), Bandwidth (100-12000 cents, default 600).
- **Note:** Bandwidth is in cents, not Hz — 1200 cents = 1 octave.
- **Detail sheet:** `plugins/aubandpass.md`

### Surge XT — internal filters (per instrument, not as an effect)

- **Character:** each Surge XT synth instance has built-in filters (Filter Cutoff/Resonance) — use `set_plugin_param` to sweep them.
- **Best for:** filter sweeps on synth patches without adding a separate filter plugin.
- **How to use:** After loading Surge XT on a channel, `set_plugin_param(channel_id, param_name="Filter Cutoff", value=<0.0-1.0>)` to sweep the filter.

## Common recipes

- **Telephone vocals:** AUBandpass at Center 1500 Hz, Bandwidth 1200 cents.
- **Radio vocals:** AUBandpass at Center 2000 Hz, Bandwidth 800 cents.
- **Underwater/muffled effect:** For a low-pass feel, we'd need a proper LP filter — currently limited (see What we're missing below).
- **Filter sweep on synth:** Use Surge XT's built-in Filter Cutoff via `set_plugin_param`.

## Comparisons

- **AUBandpass vs Surge XT internal filter:** AUBandpass is an insert effect on any channel; Surge internal is per-synth-instance only.

## What we're missing

- No general-purpose low-pass filter plugin
- No high-pass filter plugin
- No creative filter effects (Xfer LFOTool, Ohmforce Frohmage, etc.)

**Recommendation:** for low-pass/high-pass sweeps that aren't on a Surge XT channel, we're stuck. Adding a free filter plugin (or just leveraging Surge XT Effects with the appropriate FX Type) would fill this gap.
