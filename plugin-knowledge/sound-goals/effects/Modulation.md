---
category: Modulation
type: effect
---

# Modulation

Chorus, flanger, phaser, tremolo, ring mod — modulation-based color and movement effects. Reach for these on "add chorus," "flange it," "phaser," "wobble," "tremolo," "detune," "movement," "make it wider."

## Options

### Airwindows Consolidated

- **Character:** Subtle to lush modulation; chorus and ensemble algorithms (StereoChorus, ChorusEnsemble, Ensemble, StereoDoubler) lean toward natural, vintage-style modulation rather than deep LFO-heavy effects. Melt offers more liquid, experimental modulation textures.
- **Best for:** Gentle stereo widening on guitars and pads, vintage ensemble effects on strings and keys, subtle pitch movement for warmth, experimental liquid textures.
- **Emotional tags:** Lush, warm, vintage, dreamy, liquid.
- **Comparison:** More subtle and analog-flavored than modern deep chorus plugins; comparable to classic hardware ensemble units (Roland Dimension D territory) rather than aggressive flangers or pitch-modulation effects.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="Airwindows Consolidated", parameters={"algorithm": "Ensemble"})` for classic ensemble, or `"algorithm": "StereoChorus"` for stereo chorus width.

### Surge XT Effects — Chorus / Flanger / Phaser / Rotary algorithms

- **Character:** varies by algorithm — classic chorus is thick/wide, flanger has swept resonance, phaser has whooshing peaks, rotary emulates Leslie speaker
- **Best for:** widening synths, adding 80s pop chorus, funk phaser, retro rock rotary
- **Emotional tags:** wide, dreamy (chorus); dramatic, swirly (flanger/phaser); vintage, warm (rotary)
- **How to use:** `add_plugin_effect(channel_id="<target>", plugin_id="<Surge XT Effects id>")` then `set_plugin_param` with `param_name="FX Type"` to select. See `plugins/surge-xt-effects.md`.

## Common recipes

- **80s pop chorus on synths:** Surge Effects → Chorus, moderate rate, medium depth, wet ~0.4.
- **Funky guitar phaser:** Surge Effects → Phaser, slow rate, high feedback.
- **Leslie-style organ:** Surge Effects → Rotary, alternate slow/fast speeds.

## Comparisons

- **Chorus vs Flanger:** chorus is thicker and less pronounced; flanger is more dramatic with a sweeping metallic sound.
- **Phaser vs Flanger:** phaser has softer whooshing; flanger has metallic peaks.

## What we're missing

No dedicated free chorus/flanger/phaser plugins (TAL-Chorus-LX, MFreeFXBundle). Bundling those would give more targeted per-effect UIs vs. Surge Effects' generic wrapper.
