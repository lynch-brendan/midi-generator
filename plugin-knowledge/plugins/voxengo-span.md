---
name: SPAN
verified: true
last_updated: 2026-09-15
---

# Voxengo SPAN

Free real-time FFT spectrum analyzer from Voxengo (current v3.24). Industry-standard free tool for spotting mix problems, checking mastering, and comparing tracks. Pure visualization — does nothing to the audio.

## Modes / Views

- Spectrum display (log/linear frequency scale, adjustable slope)
- Peak / RMS / Avg output meters with headroom estimate
- Stereo Correlation Meter for phase check
- EBU R128 (LUFS) and K-system level scales
- True peak clipping detection
- Multi-channel routing: stereo / mono / mid / side / L / R, plus dual-spectrum overlays (e.g. two channels at once, or real-time vs all-time max)

## Notable parameters

- **Block Size** — FFT window in samples (typ. 512–16384). Bigger = better low-freq resolution but more smearing and latency; smaller = snappier, less low-end detail.
- **Overlap** — FFT window overlap %. Higher overlap = smoother display (e.g. 93.8% for very smooth).
- **Slope** — spectrum visual tilt. Default is +4.5 dB/oct so pink noise reads roughly flat; set to 0 to match level-meter power.
- **Smooth** — visual smoothing in octaves. Cosmetic only, doesn't affect measurement.
- **Avg Time** — averaging window in ms (higher = slower, more stable readout; ~6000 for near-static analysis).
- **Ballistics** — attack/release of the peak meters.
- **Secondary spectrum** — overlay of max-hold or long-term-avg curve.

## Quirks

- Zero audible effect — pure analyzer. Latency equals the FFT block size.
- Best on the master or a dedicated inspection bus, not on every track.
- Top-left readout shows exact Hz, dB, and nearest musical note under the cursor.
- Presets are managed inside Voxengo's own GUI (save/load), not via the VST3 program API.

## Best uses

- Mastering: watching LUFS + true peak, spotting resonances, checking stereo/mid-side balance
- Mixing: A/B against a reference track on the master bus
- Debugging low-end mud (block size 4096+, inspect 100–300 Hz)
- Catching phase issues live with the correlation meter
