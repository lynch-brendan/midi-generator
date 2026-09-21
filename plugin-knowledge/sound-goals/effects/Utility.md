---
category: Utility
type: effect
---

# Utility

Metering, spectrum analysis, tuning, volume adjustment, gain staging. Reach for these on "meter," "analyze," "check the levels," "tuner," "gain."

## Options

### AUSampler

- **Character:** Neutral and transparent — the sampler itself imparts no color; timbre is 100% determined by the loaded sample content (.aupreset / .exs / .sf2 / .dls).
- **Best for:** Programmatic MIDI-driven sample playback in macOS/iOS apps and DAW sessions (GarageBand, Logic, MainStage); loading EXS24 or SoundFont libraries; embedding a lightweight sampler engine in Core Audio / AVAudioEngine projects.
- **Emotional tags:** Neutral — depends entirely on loaded content.
- **Comparison:** Functionally similar to a stripped-down version of Logic's EXS24/Sampler, but with fewer parameters exposed, no built-in browser, and significant undocumented internals; more limited than full-featured samplers like Kontakt or UVI Workstation.
- **How to use:** `load_instrument(channel_id=..., plugin_id="AUSampler", preset_name="<path_to.aupreset>")` — note that the plugin will be silent until a valid instrument file is loaded.

### Airwindows Consolidated

- **Character:** A plugin-selector meta-tool housing 500+ algorithms; as a utility it offers console bus systems (ConsoleX, ConsoleH channel/buss pairs for summing coloration), monitoring tools (Monitoring3 with headphone crossfeed), stereo manipulation (PurestDualPan), and gain utilities (PurestGain). The overall plugin itself functions as a utility framework for the entire Airwindows ecosystem.
- **Best for:** Console emulation/summing color via ConsoleX channel+buss pairs, headphone mix monitoring (Cans crossfeed in Monitoring3), precision gain staging (PurestGain), stereo pan management.
- **Emotional tags:** Transparent, functional, professional, workflow-oriented.
- **Comparison:** Console system algorithms compete with paid console emulation bundles (SSL/API channel strips); monitoring algorithms fill a role similar to standalone crossfeed tools like Goodhertz CanOpener but at no cost.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="Airwindows Consolidated", parameters={"algorithm": "Channel9"})` on each channel and `"algorithm": "Console9Buss"` on the master for console emulation; `"algorithm": "Monitoring3"` on the master for headphone monitoring.

### AUSoundIsolation

- **Character:** Clean, surgical, ML-based source separation. Transparent at moderate settings; sterile and artifact-prone when pushed. Not a coloration tool — it removes rather than shapes.
- **Best for:** Removing background noise (fans, room tone, street noise) from spoken-word/vocal recordings, isolating or attenuating lead vocals for karaoke-style stems, cleaning up podcast or dialogue tracks in post.
- **Emotional tags:** Clinical, clean, dry, intelligible, utilitarian.
- **Comparison:** Similar in intent to Klevgrand Brusfri or iZotope RX Voice De-noise / Music Rebalance, but far less controllable — a single isolation amount vs. RX's spectral tools. It's the same engine behind Apple Music Sing's vocal attenuation.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUSoundIsolation")` — then sweep the wet/dry isolation slider from mostly-dry upward until noise/vocals are attenuated without audible artifacts. Best placed first in the chain, before any creative processing.

### AUSampleDelay

- **Character:** Transparent, clinical, zero-coloration. Pure sample-accurate time shift with no feedback, filtering, or mix control.
- **Best for:** Phase-aligning multi-mic drum recordings, compensating for plugin latency, nudging tracks by sub-millisecond amounts, aligning parallel processing chains, live-sound speaker delay.
- **Emotional tags:** None — this is a technical alignment tool, not a creative effect.
- **Comparison:** Unlike AUDelay (which sets time in seconds and is meant for echoes), AUSampleDelay works in samples for sample-accurate work. Similar in purpose to Voxengo Sound Delay or Waves InPhase Sample Delay, but far more minimal.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUSampleDelay", params={"Delay": <samples>})` — remember that samples-to-ms depends on session sample rate (e.g. 44 samples ≈ 1 ms @ 44.1 kHz).

### AURogerBeep

- **Character:** Novelty walkie-talkie / CB-radio "roger beep" — a short tonal chirp fired when the input drops below a threshold. Not tonal shaping, not a musical processor.
- **Best for:** Glitch/SFX transitions, faux-radio comms textures on vocals or drums, sound-design accents at the tails of phrases, and podcast/foley-style two-way-radio effects.
- **Emotional tags:** quirky, retro, comedic, sci-fi, lo-fi, gimmicky
- **Comparison:** Far more niche than typical utility plugins; where Apple's AUDelay or AUSampleDelay do broadly useful jobs, AURogerBeep is a one-trick novelty closer in spirit to walkie-talkie SFX toys than to a mixing tool. No real "warmer/darker" analog; it either fits the joke or it doesn't.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AURogerBeep", params={"In Signal Db": -30, "Sensitivity": 0.5, "Beep Frequency": 1000})` — place after the source, automate/gap the input so the signal actually drops below `In Signal Db` to trigger the beep.

No dedicated utility plugins currently installed.

## What we're missing

- No spectrum analyzer (Voxengo SPAN — free, industry-standard)
- No tuner plugin
- No dedicated gain/trim plugin (Airwindows PurestGain — free)
- No loudness meter (LUFS)

**Recommendation:** for now, the AI can't help with objective analysis (spectrum, LUFS). This is a real gap for mix/master feedback workflows. Bundling Voxengo SPAN (free) would immediately give the AI spectrum-analysis awareness — it could suggest "your low end looks muddy around 200 Hz" if it could read a spectrum.

## Common recipes

None — this category is currently empty.

## Comparisons

None — this category is currently empty.
