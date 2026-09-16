---
name: AULowpass
verified: false
last_updated: 2026-09-16
---

# AULowpass

Apple's built-in AudioUnit resonant lowpass filter — a simple 2-parameter utility filter shipped with macOS.

## Presets on disk
Not applicable — no factory preset library. AULowpass is a stock Apple AudioUnit with only two parameters; hosts may save user presets via the standard AU state API.

## Notable parameters
- **CutoffFrequency** — Hz, range 10 Hz to Nyquist (SampleRate/2), default 6900 Hz. Frequencies below this pass through; frequencies above are attenuated.
- **Resonance** — dB, range −20 to +40, default 0. Boosts (or cuts) frequencies right around the cutoff; higher values accentuate the cutoff and can produce a pronounced peak.

## Quirks
- Ships as a stock Apple AudioUnit — available in any AU host on macOS (Logic, GarageBand, FCP, etc.), but often overlooked in favor of nicer third-party filters or Logic's own Channel EQ.
- Automating cutoff/resonance can produce zipper noise or artifacts on some hosts/older macOS versions; smooth automation curves are recommended (this issue has been noted by users automating the plugin in Logic).
- Final Cut Pro has historically failed AU validation on the built-in Apple filters (including AULowpass) in some system configurations, excluding them from use until re-validated.
- The maximum useful cutoff is bounded by the session sample rate (Nyquist), not a fixed 20 kHz.
- No drive, no filter-slope selector, no filter-type switch — it is strictly a resonant lowpass. Use AUHipass / AUBandpass / AUFilter for other shapes.
