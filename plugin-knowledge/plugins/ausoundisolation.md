---
name: AUSoundIsolation
verified: false
last_updated: 2026-09-16
---

# AUSoundIsolation

Apple's undocumented system Audio Unit that uses an on-device neural network to isolate/attenuate vocals or remove background noise from an audio signal.

## Presets on disk
Not applicable — no factory preset library. This is a system-provided Apple AU (subtype `vois`, manufacturer `appl`) with no user-facing preset browser.

## Notable parameters
- **Wet/Dry (Isolation amount):** Controls how aggressively the model separates the target signal from the rest. At extreme settings the output becomes noticeably sterile/artifacted.
- **NeuralNetModelNetPathBase / NeuralNetModelNetPathBaseOverride:** Internal properties pointing to the neural-network weights the unit loads (`aufx-nnet-appl.plist`). Not exposed as user parameters.
- **DereverbPresetPathOverride:** Internal property; disabled (null) by default in Apple's own use.

(Apple ships no public parameter documentation; hosts generally expose only a single isolation/mix slider.)

## Quirks
- **Undocumented & beta:** Silently introduced in macOS 13 / iOS 16 with no public Apple documentation beyond a header constant. Marked beta by Apple.
- **Not a musical effect:** Designed for voice isolation / vocal attenuation (it is the backbone of Apple Music Sing's karaoke feature) and for Continuity Camera's Voice Isolation — not for creative sound design.
- **Host incompatibility:** Many hosts (e.g. Audacity) fail to instantiate it — it reports `could not initialize component` during AU scans and is flagged as incompatible.
- **Requires the system neural network to load:** Depends on the on-device model weights being resolvable via `NeuralNetModelNetPathBase`; if the path isn't set up, the unit won't process.
- **Pushing wet too far:** Produces heavy artifacts / a "painfully sterile" sound; also mangles distorted vocals or tracks where instruments overpower the voice, since the model does not use lyric data.
- **On-device only:** All processing runs locally; behavior may differ across Apple Silicon vs Intel and across OS versions as Apple updates the model.
