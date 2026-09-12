---
category: Pitch
type: effect
---

# Pitch

Pitch correction, harmonizers, pitch shifters, vocoders. Reach for these on "Auto-Tune," "pitch correct," "harmonize," "pitch shift," "vocoder," "T-Pain effect," "make the vocals in tune."

## Options

### Auto-Tune Pro (Antares) — industry-standard pitch correction

- **Character:** varies by Retune Speed — natural correction (60+) to obvious T-Pain effect (0-20)
- **Best for:** correcting mic recordings, creating the classic Auto-Tune sound on vocals
- **Emotional tags:** clean (natural), digital/robotic (fast retune), stylized (T-Pain style)
- **Presets:** Vocal - Lead, Vocal - Backing, Classic Auto-Tune, Robot, and others
- **How to use:** `add_plugin_effect(channel_id="<vocal channel>", plugin_id="<Auto-Tune Pro id>", preset_name="<preset>")`. Key parameters: Retune Speed (aka Speed), Flex-Tune, Humanize, Key.
- **Caveat:** Does nothing on channels without audio input (i.e., pointless on MIDI-only synth channels — only useful on mic recordings or audio clips playing through).
- **Detail sheet:** `plugins/auto-tune-pro.md`

## Common recipes

- **Natural vocal correction (invisible):** Auto-Tune Pro with preset "Vocal - Lead", Retune Speed 60+.
- **Classic T-Pain effect:** Auto-Tune Pro preset "Classic Auto-Tune" or "Robot", Retune Speed 0-10.
- **Modern rap Auto-Tune (Travis Scott style):** Retune Speed ~15-25, Humanize ~30.

## Comparisons

- **Auto-Tune Pro at Speed 60 vs Speed 10:** slow (60+) is transparent/natural. Fast (0-20) is the audible Auto-Tune sound.

## What we're missing

- No Waves Tune Real-Time or Melodyne (paid, but industry-standard alternatives)
- No harmonizer plugin (creates parallel voices in a scale)
- No vocoder (Surge XT Effects has vocoder mode but hard to automate)
- No formant shifter

**Recommendation:** Auto-Tune Pro covers the correction use case well. If the user wants harmonies, we'd need a dedicated harmonizer plugin.
