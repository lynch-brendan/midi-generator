---
category: EQ
type: effect
---

# EQ

Frequency shaping — cut lows, boost highs, notch feedback, carve space. Reach for these on "EQ," "boost the highs," "cut the mud," "brighter," "warmer," "roll off the lows," "sharpen."

## Options

### Airwindows Consolidated

- **Character:** Unconventional, DSP-first EQ designs; ranges from the extremely approachable (SmoothEQ3) to experimental averaging-based filters (Average, AverMatrix) and parametric biquad stacks (BiquadStack, Parametric). Tonal character tends toward smooth, musical, and phase-coherent rather than surgical.
- **Best for:** Gentle tonal shaping and color, experimental filter-as-effect applications, mixing EQ where character matters over precision, console-integrated EQ via ConsoleX channel algorithms.
- **Emotional tags:** Smooth, musical, analog-flavored, subtle.
- **Comparison:** Not a replacement for a fully-featured surgical EQ (no spectrum analyzer, limited band counts on most algorithms); better compared to "color EQ" plugins like Pultec emulations or Neve-style EQs in terms of workflow philosophy. BiquadStack offers more conventional parametric functionality.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="Airwindows Consolidated", parameters={"algorithm": "SmoothEQ3"})` for approachable tonal shaping, or `"algorithm": "Parametric"` for a three-band Console-X-based EQ.

### AUParametricEQ

- **Character:** Clean, transparent, surgical. A textbook digital peaking EQ with no added color, saturation, or analog modeling.
- **Best for:** Precise single-band cuts or boosts — notching resonances, taming a harsh frequency, adding a small presence bump. Chain multiple instances for multi-band shaping.
- **Emotional tags:** neutral, clinical, corrective, utilitarian
- **Comparison:** Far more basic than FabFilter Pro-Q or Logic's Channel EQ (single band vs. many, no visual curve). Cleaner and more neutral than analog-modeled EQs like Waves SSL or UAD Pultec — no character, just math. Comparable in spirit to a single band of ReaEQ.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUParametricEQ", params={"CenterFreq": 2000, "Q": 1.0, "Gain": 0.0})`

### AUNBandEQ

- **Character:** Clean, transparent, digital/surgical. No analog coloration — a neutral tool for both corrective and tonal EQ work.
- **Best for:** Free, always-available multi-band parametric EQ on macOS/iOS. Up to 16 bands with a full menu of filter types (parametric bell, Butterworth LP/HP, resonant LP/HP, bandpass, bandstop, low/high shelf, resonant shelves) — good for HPF/LPF cleanup, broad tonal shaping, notching resonances, or as a lightweight mixing/mastering EQ when a third-party plugin isn't available. Also commonly used for system-wide/room-correction EQ inside AU Lab.
- **Emotional tags:** neutral, clinical, precise, utilitarian.
- **Comparison:** Sonically transparent like FabFilter Pro-Q or Logic's Channel EQ, but with a bare-bones UI and no spectrum analyzer. More flexible (more filter types, more bands) than AUGraphicEQ or a simple 6-band EQ like SimplEQ, but far less visual and workflow-friendly than Pro-Q 3 or TDR Nova. No analog character à la Pultec/SSL/Neve emulations.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUNBandEQ", manufacturer="Apple", format="AudioUnit")` — then set per-band `filter_type`, `frequency` (Hz), `bandwidth` (octaves, not Q), `gain` (dB), and `bypass`. Remember to convert Q→BW when porting settings from Q-based EQs.

### AULowShelfFilter

- **Character:** Clean, transparent, surgical — a plain digital shelf with no coloration, saturation, or analog character.
- **Best for:** Quick low-end shaping when you need a no-nonsense shelf: taming sub rumble, adding weight to a thin bass, gentle low-end lift on a bus, or as a lightweight CPU-friendly tone control in utility chains.
- **Emotional tags:** neutral, clinical, utilitarian
- **Comparison:** More basic and more transparent than FabFilter Pro-Q, Logic's Channel EQ, or any analog-modeled shelf (Pultec, SSL). No harmonic character like Waves RBass or MaagEQ. Think of it as the low-shelf band of a stock parametric EQ, exposed as a standalone plugin.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AULowShelfFilter", params={"Cutoff Frequency": 80, "Gain": 3.0})`

### AUHighShelfFilter

- **Character:** Clean, transparent, utilitarian — a basic digital high-shelf with no coloration or saturation.
- **Best for:** Quick top-end boost or cut (air band, de-harshing); simple tone-shaping when a full parametric EQ is overkill; scripted/automated tonal adjustments in AU-hosted workflows.
- **Emotional tags:** neutral, clean, surgical, functional.
- **Comparison:** Far more limited than FabFilter Pro-Q, Logic's Channel EQ, or TDR Nova — no Q, no multiple bands, fixed shelf shape. Think of it as the AU equivalent of a single-band shelf utility rather than a mixing EQ. Cutoff range is skewed high (~10 kHz+), so it's really an "air shelf" more than a general-purpose high shelf.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUHighShelfFilter")` then set `Cutoff Frequency` (Hz) and `Gain` (dB).

### AUGraphicEQ

- **Character:** Clean, transparent, utilitarian — no coloration or analog character. Sounds like what you'd expect from a stock digital graphic EQ.
- **Best for:** Quick broad tone-shaping, corrective cuts across ISO bands, live-style graphic EQ moves (smiley curves, telephone/lo-fi filters by pulling extreme bands), rough tonal sculpting on busses or full mixes.
- **Emotional tags:** neutral, clinical, practical, no-nonsense
- **Comparison:** More basic and less musical than FabFilter Pro-Q or Logic's Channel EQ; lacks the surgical parametric control of those tools but faster for quick broad-stroke moves. Similar in concept to a hardware 31-band graphic EQ but without any analog warmth. Less colored than Waves GEQ or API-style graphic EQs.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUGraphicEQ", preset_name="...")`

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
