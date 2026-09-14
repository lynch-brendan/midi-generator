---
name: FL Studio
verified: false
last_updated: 2026-09-14
---

# FL Studio (VSTi wrapper)

Image-Line's FL Studio distributed as an AudioUnit — the full FL Studio
hosted as a plugin inside another DAW. Requires FL Studio installed on
the user's Mac. For FL owners, this unlocks their entire toolkit inside
Nasty: **Sytrus, FLEX, Sakura, Harmor, Slicex, all their FL presets,
plus the Fruity effects (Fruity Reverb, Fruity Delay, Maximus, Edison).**

## The FL-in-Nasty pattern

Load FL Studio VSTi on a channel. Its GUI opens FL's mixer/channel-rack
inside a window. Producer picks a preset inside FL (e.g., load Sytrus
with a preset). Nasty routes MIDI notes to it. Nasty's arrangement view
drives playback. FL VSTi becomes the "sound source folder" — not a
full DAW-inside-a-DAW.

## Presets

FL Studio VSTi exposes its state through the standard host state save
(setStateInformation) rather than a `presets` array. To pre-load a
specific FL instrument + preset, the user typically opens FL VSTi's GUI
and picks the plugin + preset there. Nasty can then play notes and
the sound comes from whichever instrument is loaded inside FL.

## Notable parameters

FL VSTi exposes a fixed number of automation slots to the host (128).
Each slot is a knob inside FL Studio that the producer has "linked" to
the host's automation slot via right-click → "Link to controller."

Without user linking, only top-level params (main volume) are visible.
For deep knob control ("turn the Sytrus filter cutoff"), the producer
does a one-time link inside FL — after that the AI can turn that knob.

## Quirks

- **Requires FL Studio installed.** Not standalone.
- **Nested-DAW UX.** Opening FL VSTi launches FL Studio inside a window.
  Beatmakers use it as a sound-source browser, not a full DAW workflow.
- **Historically crashy.** Prior to the message-thread deadlock fix
  (2026-09-13), loading FL VSTi could deadlock the engine because FL's
  init pumps the message loop while our host held MessageManagerLock.
  With that fix, load should now succeed. If crashes recur, the
  workflow is: save song → relaunch Nasty → reload. Song state (patterns,
  arrangement) survives; the plugin state that was loaded inside FL is
  restored from the plugin's serialized state.
- **Audio through FL's mixer.** FL VSTi has its own master output.
  Route it into Nasty's mixer as a normal channel.

## When to load FL VSTi

- User owns FL Studio and asks for a Sytrus/FLEX/Harmor/etc. sound —
  load FL VSTi, tell the user to pick the specific instrument inside.
- User wants to bring an FL project into Nasty — load FL VSTi and open
  their .flp file inside.
- Do NOT load FL VSTi for random synth requests when Surge XT, Dexed,
  Odin 2, or the bundled OSS synths would answer the same request without
  requiring an external DAW.
