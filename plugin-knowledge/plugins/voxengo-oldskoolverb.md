---
name: OldSkoolVerb
verified: true
last_updated: 2026-09-15
---

# Voxengo OldSkoolVerb

Free classic algorithmic stereo reverb from Voxengo (current v2.14). Simple,
optimal reverb algorithm that covers plates, rooms, and halls with a clean
spatial image that sits in a mix without hogging space. Mid-2000s design,
still a workhorse "just put a reverb on it" plugin. Free.

## Notable parameters

- **Mode** — 5 algorithm presets (plate, room, hall variants). Sets the
  underlying reflection pattern; other params tweak it.
- **Space** — ms between reflections; effectively room dimensions. Low
  values = dense plate-like tail, high values = sparse hall.
- **Time** — RT60 in milliseconds (how long the tail decays).
- **Pre-Delay** — ms before the wet signal starts. Models listener distance.
- **Damp Lo** — low-frequency damping corner (Hz). Cuts rumble in the tail.
- **Damp Hi** — high-frequency damping corner (Hz). Rolls off the top of
  the tail so it feels warmer / older.
- **Width** — stereo spread of the reverb (%).
- **Reverb** / **Dry** — wet and dry gain in dB (independent, not a single
  mix knob).

## Quirks

- Voxengo house UI — small, functional, not pretty. Resizable.
- Very CPU-light; fine to instantiate on many tracks.
- Zero processing latency, 64-bit internal.
- No IR loading — this is purely algorithmic. If you need convolution use
  a different plugin.
- "OldSkoolVerb Plus" is a separate paid variant with extra EQ / envelope
  controls. Free version is what most users have.
- Presets managed via Voxengo's own preset manager inside the GUI, not
  exposed as VST3 programs.

## Best uses

- Vocal plate (Mode = plate, Space low, Time ~1.5s, Damp Hi ~6kHz)
- Drum room (Mode = room, Time 0.3–0.5s, Pre-Delay 10–20ms, Damp Hi ~4kHz)
- Guitar / synth glue (Mode = hall, Width 100%, low Reverb gain for subtle
  wash)
- Full-mix ambience (Mode = hall, Space high, Time 1.8–2.5s) — the sparse
  tail was literally designed to sit over a full mix
