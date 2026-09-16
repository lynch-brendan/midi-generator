---
category: Saturation
type: effect
---

# Saturation & Distortion

Harmonic addition — warmth, grit, fuzz, tape saturation, tube warmth, bitcrush. Reach for these on "make it warmer," "add grit," "distort," "saturate," "crunchier," "dirty it up," "add tube warmth," "bitcrush," "lo-fi it."

## Options

### AUDistortion

- **Character:** Digital, gritty, and often extreme — a multi-stage effect that can range from mild crunch through bitcrushed lo-fi to clangy, metallic ring-modulated destruction. Not a warm analog-style saturator; sounds distinctly digital.
- **Best for:** Aggressive lo-fi textures, sci-fi/robotic voice effects, bell-like inharmonic tones via the ring mod stage, bitcrushed drums and synths, sound-design mangling on macOS-only sessions.
- **Emotional tags:** aggressive, harsh, alien, robotic, broken, industrial, sci-fi
- **Comparison:** Much more extreme and digital-sounding than typical tape/tube saturators (Decapitator, Saturn); closer in spirit to a combined bitcrusher + ring modulator than to a guitar amp. Free and always-available on macOS, but less musical/refined than dedicated third-party distortion plugins.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUDistortion", preset_name="...")`

### Surge XT Effects — Distortion / Overdrive / Waveshaper

- **Character:** varies by algorithm — soft-clip warmth, hard-clip aggression, waveshaper for harmonic richness, bitcrusher for lo-fi digital grit
- **Best for:** any dirt/warmth need — subtle saturation to full-on distortion
- **Emotional tags:** warm (soft-clip), aggressive (hard-clip), digital (bitcrush), gritty (waveshaper)
- **How to use:** `add_plugin_effect(channel_id="<target>", plugin_id="<Surge XT Effects id>")` then `set_plugin_param` with `param_name="FX Type"` to select algorithm. See `plugins/surge-xt-effects.md`.

## Common recipes

- **Tape warmth on drums/master:** Surge Effects with a gentle soft-clip / saturation algorithm, low drive.
- **Aggressive bass distortion:** Surge Effects → hard-clip or waveshaper, high drive amount.
- **Lo-fi bitcrush on vocals:** Surge Effects → bitcrusher, adjust bit depth and sample rate reduction for the vibe.

## Comparisons

Only Surge Effects available in this category — internal algorithm choice provides the character range.

## What we're missing

- No dedicated Klanghelm IVGI (free tape/tube saturation)
- No Airwindows Consolidated (free, hundreds of saturation flavors)
- No SoftUbe or dedicated tube saturation plugins

**Recommendation:** if the user asks for tape warmth specifically, we can use Surge Effects but a dedicated Klanghelm IVGI would sound more authentic. Consider bundling.
