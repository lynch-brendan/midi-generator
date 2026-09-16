---
name: AUPeakLimiter
verified: false
last_updated: 2026-09-16
---

# AUPeakLimiter

Apple's built-in macOS Audio Unit peak limiter — a simple, transparent brick-wall style limiter used to prevent clipping and raise perceived loudness.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API. <cite index="7-10">AUPeakLimiter is a peak limiter shipped by Apple as a system Audio Unit (subtype kAudioUnitSubType_PeakLimiter).</cite>

## Notable parameters
- **Attack Time** — <cite index="11-1">Global, seconds, range 0.001 → 0.03, default 0.012 (kLimiterParam_AttackTime)</cite>
- **Decay Time** — <cite index="11-1">Global, seconds, range 0.001 → 0.06, default 0.024 (kLimiterParam_DecayTime)</cite>
- **Pre-Gain** — <cite index="11-1">Global, dB, range -40 → 40, default 0 (kLimiterParam_PreGain)</cite>. Boosting Pre-Gain drives the signal harder into the limiter, increasing perceived loudness.

## Quirks
- <cite index="9-11,9-12,9-13">The AUPeakLimiter gives no "Max Peak" / output ceiling setting — it assumes you want the resulting peak to hit 0 dB, so if you only run AUPeakLimiter your audio will not meet specs that require peaks below a specific ceiling (e.g. -3 dB).</cite> To hit a custom ceiling you must follow it with a gain/amplify stage.
- Only three parameters: Attack, Decay, Pre-Gain. There is no threshold, ratio, release curve, or lookahead control.
- <cite index="2-2,2-3">Intended to limit the maximum volume of audio to prevent clipping; commonly used to increase perceived loudness without distortion.</cite>
- Not a coloration/character limiter — it's a clean utility limiter, not a mastering-grade tool.

## Common recipes (optional)
- **Prevent clipping on a bus:** Attack ~0.012 s, Decay ~0.024 s, Pre-Gain 0 dB — insert last on the chain as a safety catch.
- **Loudness push:** raise Pre-Gain in 1–3 dB steps until the material sits at the desired loudness; shorten Attack for tighter peak control, lengthen Decay to reduce pumping.
