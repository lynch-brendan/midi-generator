---
name: TAL Reverb 4 Plugin
verified: true
last_updated: 2026-09-15
---

# TAL-Reverb-4

Free plate-style reverb from Togu Audio Line. Warm, smooth,
"always-on-tap" tails — the sound of a physical steel plate reverb
without the plate. A workhorse in producer circles for vocals, snares,
and general glue.

## Notable parameters

- **Pre Delay** — ms before the reverb tail begins. Higher values keep
  the dry signal upfront and readable.
- **Decay Time** — RT60 length of the tail.
- **Size** — plate dimension. Bigger size = later reflections, longer
  natural decay.
- **Diffuse** — smoothness of early reflections vs discrete echoes.
  High = classic smooth plate wash; low = grainier, more slapback.
- **Damp** — high-frequency rolloff of the tail (added in v4.0.2).
  Darker plates as damp goes up.
- **Modulation Rate / Amount** — subtle chorus on the tail; keeps long
  reverbs alive and avoids metallic ringing.
- **Low Cut / High Cut (EQ section)** — pre-reverb filter to keep bass
  out of the tail and tame highs.
- **Tune** — pitch shifter on the tail. Small amounts = shimmer; larger
  = distinctly detuned/dissonant.
- **Ducking** — sidechain-style tail attenuation while the input is
  playing. Great for vocals.
- **Dry / Wet** — mix balance.
- **Stereo Width** — wet signal spread.
- **Bit / Sample Rate** — lo-fi tail degradation (added in v4.0.2).

## Quirks

- Plate character — smoother than a hall, less "roomy" than a chamber.
  Classic pop/rock/soul vocal sound; won't sell "big room."
- CPU-light; safe to run on many tracks.
- Presets are file-based, not exposed via standard VST3 program API.
  On macOS they live at
  `~/Library/Audio/Presets/TAL-Togu Audio Line/TAL Reverb 4 Plugin/`.
  In-plugin: click "Default" at the top and choose "Show Presets Folder"
  to reveal the exact path.
- Factory preset bank ships alongside the plugin; users can drop
  third-party preset packs into that folder.
- Reports itself as "TAL Reverb 4 Plugin" (with spaces) in the VST3
  identifier — worth knowing for scan/detect code.

## Best uses

- Lead vocal plate — decay ~1.8–2.2s, pre-delay 20–40ms, high cut
  around 7 kHz, ducking on.
- Snare plate — short decay ~0.6s, tight size, high diffuse.
- Piano / Rhodes / keys ambience — modest wet, medium decay.
- Guitar wash — higher modulation for movement, moderate size.
- Anywhere you'd historically reach for an EMT 140.
