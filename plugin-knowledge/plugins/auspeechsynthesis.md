---
name: AUSpeechSynthesis
verified: false
last_updated: 2026-09-16
---

# AUSpeechSynthesis

Apple's built-in macOS system Audio Unit that generates speech from text using the OS text-to-speech engine.

## Presets on disk
Not applicable — no factory preset library. This is a system-provided AU installed at `/System/Library/Components/AUSpeechSynthesis.component/`. Any user presets saved via a host would land in `~/Library/Audio/Presets/Apple/AUSpeechSynthesis/` as `.aupreset` files.

## Notable parameters
Exposes text input and voice selection tied to the macOS Speech Synthesis system voices (e.g. Alex, Samantha, Fred, Victoria). Parameter set is minimal and host-dependent; most hosts show only a basic text field and voice picker rather than musical controls (pitch/rate are not consistently exposed as automatable AU parameters).

## Quirks
- **Frequently silent / non-functional in third-party hosts.** Users report loading it in hosts like Plogue Bidule and being unable to get any audio output from it. It is primarily designed for system use, not DAW production.
- **Known to crash or throw errors in GarageBand and Logic** on some macOS versions; Apple's own guidance is that if the component is corrupted the OS must be reinstalled since it ships as part of the system.
- **Not a musical instrument** — it does not respond to MIDI note input in a pitched way. Output is spoken text, not tonal notes.
- **Not routable in many modern DAWs** on Apple Silicon; the component is legacy and increasingly deprecated in favor of `AVSpeechSynthesisProviderAudioUnit` on newer macOS.
- Historically caused validation failures when wrapped by tools like Novation Automap.
- No factory presets; state consists of whatever text/voice the host stores.

## Common recipes (optional)
Not applicable — this is a speech synthesizer, not a musical synth. If it does produce audio in your host, feed it short phrases and process heavily with pitch-shift, vocoder, reverb, or granular effects for robotic/glitch vocal textures.
