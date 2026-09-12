---
category: EQ
type: effect
---

# EQ

Frequency shaping — cut lows, boost highs, notch feedback, carve space. Reach for these on "EQ," "boost the highs," "cut the mud," "brighter," "warmer," "roll off the lows," "sharpen."

## Options

### AUBandpass (Apple, ships with macOS) — narrow bandpass filter, not a true EQ

- **Character:** bandpass filter, isolates a single frequency band
- **Best for:** creative filter effects, feedback removal at a specific frequency, telephone/radio filter sounds
- **Emotional tags:** filtered, radio-like, telephonic, focused
- **How to use:** `add_plugin_effect(channel_id="<target>", plugin_id="<AUBandpass id>")`. Parameters: CenterFrequency (20 Hz - Nyquist), Bandwidth (100 to 12000 cents).
- **Detail sheet:** `plugins/aubandpass.md`
- **Caveat:** This is a filter, NOT a full multi-band EQ. Use for creative effects, not general tone shaping.

## What we're missing

**No general-purpose multi-band EQ is currently installed.** For "boost the highs / cut the low mids / carve space" requests, we can't currently do it. This is a real gap.

- No TDR Nova (free dynamic EQ — industry-standard free option)
- No TDR SlickEQ (free tone-shaping EQ)
- No ReaEQ (free parametric)

**Recommendation:** if the user asks for EQ, be honest that we only have a bandpass filter available and suggest they download TDR Nova or SlickEQ for proper multi-band EQ work.

## Common recipes (with what we have)

- **Telephone/radio effect on vocals:** AUBandpass at Center 1500 Hz, Bandwidth 1200 cents.
- **Isolate a frequency band creatively:** AUBandpass at desired Center with narrow Bandwidth.

## Comparisons

Nothing to compare — only AUBandpass exists in this category currently.
