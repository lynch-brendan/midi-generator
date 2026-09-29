---
name: MasterLimiter
verified: false
last_updated: 2026-09-29
---

# MasterLimiter

Brickwall mastering limiter effect plugin by "Nasty" — identity and full feature set could not be verified from available public sources.

## Presets on disk

Not applicable — no verifiable preset library found. Preset handling (if any) is likely via the standard VST/AU program API.

## Notable parameters

> ⚠️ The specific parameter names for this plugin could not be confirmed from any official documentation, review, or forum discussion. The following are generic parameters common to brickwall limiter plugins of this type and should be treated as **unverified estimates**:

- **Threshold** — Sets the level at which limiting begins; lowering it increases loudness
- **Output Ceiling** — Hard ceiling (typically 0 dBFS or -0.1 dBFS) that the signal cannot exceed
- **Release** — Controls how quickly the limiter recovers after gain reduction
- **Gain / Input Gain** — Drives more signal into the limiter for increased loudness

## Quirks

- **Manufacturer identity unclear:** No plugin called "MasterLimiter" by a manufacturer named "Nasty" could be located in KVR Audio, plugin databases, reviews, or forum discussions as of 2026-09-29. This may be an internal/proprietary plugin, a DAW-bundled effect, or a misidentified plugin.
- **Do not assume parameter names** match the generic list above — verify in the plugin's own UI before automation.
- If this is the Reaper JS "masterLimiter" (by LOSER, shipped with ReaPlugs), it is a zero-latency JS script effect and not a standalone VST3/AU — it has no file-based presets and very few parameters.
- If this is the HOFA SYSTEM MasterLimiter, it is a different manufacturer and has its own verified parameter set not attributed to "Nasty".

## Common recipes

Not applicable — effect plugin, not an instrument.
