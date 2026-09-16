---
category: Filters
type: effect
---

# Filters

Low-pass, high-pass, band-pass filtering — carve frequencies, do filter sweeps, telephone/radio effects. Reach for these on "filter," "low-pass," "high-pass," "sweep," "telephone effect," "radio effect," "muted," "underwater."

## Options

### AULowShelfFilter

- **Character:** Clean, non-resonant shelving filter — smooth low-frequency tilt with no self-oscillation or character.
- **Best for:** Static low-end tone shaping rather than performative filter sweeps. Use when you want a shelf response (tilt) instead of a cutoff-style low-pass/high-pass. Handy on sends, master utility chains, or to gently darken/brighten the bottom of a source.
- **Emotional tags:** subtle, controlled, understated
- **Comparison:** Not a creative/resonant filter like AutoFilter, Diva's filter, or Kilohearts Filter — no resonance, no envelope, no LFO. Closer in spirit to a mixer's low-shelf tone knob than to a synth filter.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AULowShelfFilter", params={"Cutoff Frequency": 120, "Gain": -6.0})`

### AULowpass

- **Character:** Clean, neutral, utilitarian. A basic resonant lowpass with no analog coloration or drive — it simply removes highs above the cutoff and can add a resonant peak at the cutoff.
- **Best for:** Quick tone-shaping tasks — muffling a track to sound distant/underwater, taming harshness, simulating "music heard from outside a club," DJ-style filter sweeps, or removing high-frequency noise. Useful as a lightweight always-available filter when no third-party plugin is needed.
- **Emotional tags:** muffled, distant, underwater, dreamy, lo-fi, veiled, dampened
- **Comparison:** Much more basic and sterile than dedicated analog-modeled filters (e.g. FabFilter Volcano, Kilohearts Filter, or the filters in Diva/Repro). No drive, no slope selection, no character — but it's stock on every Mac and CPU-cheap. Comparable in scope to AUHipass (its high-pass sibling) and simpler than AUFilter.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AULowpass", params={"CutoffFrequency": 800, "Resonance": 6})`

### AUHipass

- **Character:** Clean, transparent, surgical — no analog coloration or drive. A pure mathematical high-pass.
- **Best for:** Removing low-end rumble, cleaning up mix bus mud, tightening bass on non-bass tracks, HP-ing reverb/delay returns, basic utility filtering.
- **Emotional tags:** neutral, clean, clinical, functional
- **Comparison:** More transparent and less characterful than FabFilter Pro-Q or analog-modeled filters (Kush AR-1, UAD Pultec HPF); comparable in role to Logic's Channel EQ HP band or Reaper's ReaEQ HP, but as a dedicated single-purpose plugin. No resonance sweep musicality like a Moog ladder or Diva filter.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUHipass", preset_name=None)` then automate/set `Cutoff Frequency` and `Resonance`.

### AUFilter

- **Character:** Clean, transparent, utilitarian — no analog coloration or drive.
- **Best for:** Quick broadband tone shaping when you need a simple low-end + high-end shelf/cut combo without loading a full EQ.
- **Emotional tags:** neutral, surgical, unobtrusive
- **Comparison:** More basic than AUNBandEQ or AUParametricEQ; lacks the resonant sweepable character of dedicated filter plugins like FabFilter Volcano or Kilohearts Filter. No resonance/self-oscillation, no modulation.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUFilter")`

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
