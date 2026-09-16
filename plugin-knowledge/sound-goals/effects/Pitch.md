---
category: Pitch
type: effect
---

# Pitch

Pitch correction, harmonizers, pitch shifters, vocoders. Reach for these on "Auto-Tune," "pitch correct," "harmonize," "pitch shift," "vocoder," "T-Pain effect," "make the vocals in tune."

## Options

### AUPitch

- **Character:** Basic, utilitarian real-time pitch-shifter; clean at small shifts, gets grainy/phasey on large transpositions or complex material. Not a "colored" effect — it's a workhorse.
- **Best for:** Quick semitone/cent transposition of audio without changing tempo, transposing samples, karaoke-style key changes, small tuning corrections, creative octave shifts on FX or vocals.
- **Emotional tags:** neutral, corrective, functional; can be alien/warbly when pushed to extreme cents.
- **Comparison:** Rougher and less transparent than Logic's Pitch Shifter II, Waves SoundShifter, or Celemony/Melodyne; simpler and lower-CPU than Serato Pitch 'n Time or iZotope Radius. Free and always-available on macOS, which is its main advantage.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUPitch", params={"Pitch": 100, "Effect Blend": 100, "Smoothness": 0, "Tightness": 0})` — set Pitch in cents (±2400), keep Effect Blend at 100 for full shift, tweak Smoothness/Tightness to reduce artifacts.

### AUNewPitch

- **Character:** Clean, transparent, surgical — a no-frills real-time pitch shifter with a single Pitch Scale control measured in cents for very fine adjustments.
- **Best for:** Precise cent-level detuning, subtle pitch offsets on loops/one-shots, whole-step transposition via automation, quick tuning fixes on WAV samples that can't be transposed like Apple Loops.
- **Emotional tags:** neutral, utilitarian, precise, subtle
- **Comparison:** Simpler and more minimal than Logic's Pitch Shifter (which has Semi Tones, Cents, Mix and algorithm modes like Drums/Speech/Vocals); less musical/creative than dedicated harmonizers like Eventide Quadravox or MicroPitch, but better than Pitch Shifter when you need fine cent-resolution tuning or automatable pitch-scale sweeps.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUNewPitch")` — then automate the `Pitch Scale` parameter (in cents; 100 = one semitone, 1200 = one octave) for pitch sweeps, or set a static value for tuning correction.

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
