---
name: AUHighShelfFilter
verified: false
last_updated: 2026-09-16
---

# AUHighShelfFilter

Apple's built-in AudioUnit high-shelf filter — a simple system-provided EQ that boosts or cuts frequencies above a chosen cutoff.

## Presets on disk
Not applicable — this is an Apple system AudioUnit with no factory preset library. State can be saved/recalled via the standard AU program API by the host.

## Notable parameters
- **Cutoff Frequency** (Hz) — the shelf corner frequency, roughly 10000 Hz to 22050 Hz range on Apple's built-in high-shelf.
- **Gain** (dB) — boost or cut applied above the cutoff, typically ±40 dB range.

## Quirks
- Ships as part of macOS Core Audio; available on any Mac DAW that hosts AudioUnits. Not available on Windows.
- Very narrow cutoff range compared to a musical shelf EQ — the shelf corner starts high (around 10 kHz), so it primarily affects the top end / "air" band rather than mids.
- No Q/slope control; fixed shelf shape.
- Minimal/utilitarian GUI (generic AU parameter view in most hosts) — intended more as a building block than a production EQ.
