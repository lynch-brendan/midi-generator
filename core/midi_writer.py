"""
Pure Python MIDI binary writer — no external dependencies.
Writes MIDI Format 0 (single-track) files.
Supports pitch bend events for slides, glissandos, and vibrato.
"""
import math
import struct
from pathlib import Path
from typing import List, Dict, Any, Tuple


TICKS_PER_BEAT = 480


def _encode_vlq(value: int) -> bytes:
    """Encode an integer as a MIDI variable-length quantity."""
    if value < 0:
        raise ValueError(f"VLQ must be non-negative, got {value}")
    result = [value & 0x7F]
    value >>= 7
    while value > 0:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.reverse()
    return bytes(result)


def _semitones_to_bend(semitones: float) -> int:
    """
    Convert a semitone offset to a 14-bit MIDI pitch bend value.
    Center (no bend) = 8192. Range assumes ±12 semitones = full bend range.
    Clamped to [0, 16383].
    """
    value = 8192 + round((semitones / 12.0) * 8191)
    return max(0, min(16383, value))


def _pitch_bend_event(channel: int, semitones: float) -> bytes:
    """Return a 3-byte pitch bend message for the given channel and semitone offset."""
    ch = channel & 0x0F
    value = _semitones_to_bend(semitones)
    lsb = value & 0x7F
    msb = (value >> 7) & 0x7F
    return bytes([0xE0 | ch, lsb, msb])


def _rpn_pitch_bend_range(channel: int, semitones: int = 12) -> List[Tuple[int, bytes]]:
    """
    Return a list of (tick=0, event_bytes) tuples that set the RPN pitch bend range.
    Must be sent at the start of the track before any pitch bend events.
    """
    ch = channel & 0x0F
    cc = lambda num, val: bytes([0xB0 | ch, num, val])
    return [
        (0, cc(101, 0)),    # RPN MSB = 0
        (0, cc(100, 0)),    # RPN LSB = 0 (pitch bend range)
        (0, cc(6, semitones)),  # Data entry MSB = range in semitones
        (0, cc(38, 0)),     # Data entry LSB = 0
        (0, cc(101, 127)),  # Null RPN MSB
        (0, cc(100, 127)),  # Null RPN LSB
    ]


def _interpolate_bend_events(
    channel: int,
    start_tick: int,
    end_tick: int,
    start_semitones: float,
    end_semitones: float,
    steps: int = 10,
) -> List[Tuple[int, bytes]]:
    """
    Generate interpolated pitch bend events from start_semitones to end_semitones
    across the given tick range, using `steps` evenly spaced events.
    """
    if steps < 1:
        return []
    events = []
    for i in range(steps):
        t = i / max(steps - 1, 1)
        semitones = start_semitones + t * (end_semitones - start_semitones)
        tick = start_tick + round(i * (end_tick - start_tick) / max(steps - 1, 1))
        events.append((tick, _pitch_bend_event(channel, semitones)))
    return events


def _vibrato_events(
    channel: int,
    tick_on: int,
    tick_off: int,
    duration_beats: float,
    vibrato_depth: float,
    vibrato_delay: float,
) -> List[Tuple[int, bytes]]:
    """
    Generate sine-wave vibrato pitch bend events for a note.
    Returns empty list if the note is too short or depth is zero.
    """
    if duration_beats < 0.4 or vibrato_depth <= 0:
        return []

    RATE = 3.0          # cycles per beat
    STEP = 0.04         # beats between events
    TAIL = 0.1          # beats before note-off to stop

    vibrato_start_tick = tick_on + round(vibrato_delay * TICKS_PER_BEAT)
    vibrato_end_tick = tick_off - round(TAIL * TICKS_PER_BEAT)

    if vibrato_start_tick >= vibrato_end_tick:
        return []

    events = []
    t = 0.0  # beats since vibrato start
    while True:
        tick = vibrato_start_tick + round(t * TICKS_PER_BEAT)
        if tick >= vibrato_end_tick:
            break
        semitones = vibrato_depth * math.sin(2 * math.pi * RATE * t)
        events.append((tick, _pitch_bend_event(channel, semitones)))
        t += STEP

    return events


def _build_track_data(notes: List[Dict], tempo_bpm: int, gm_patch: int, channel: int = 0, bars: int = None) -> bytes:
    """
    Build raw MIDI track bytes from a list of note dicts.

    Each note dict must have: pitch, duration (beats), velocity, time (beats).
    Optional expressive fields per note:
      bend_start (float): semitones to slide in from at note start
      bend_end   (float): semitones to slide out to at note end
      vibrato    (float): vibrato depth in semitones
      vibrato_delay (float): beats before vibrato begins (default 0.25)

    Returns the raw event bytes (without the MTrk header/length).
    """
    us_per_beat = int(60_000_000 / max(tempo_bpm, 1))
    events: List[Tuple[int, bytes]] = []

    # Tempo meta event
    tempo_event = bytes([
        0xFF, 0x51, 0x03,
        (us_per_beat >> 16) & 0xFF,
        (us_per_beat >> 8) & 0xFF,
        us_per_beat & 0xFF,
    ])
    events.append((0, tempo_event))

    ch = channel & 0x0F

    # Set pitch bend range to ±12 semitones via RPN
    events.extend(_rpn_pitch_bend_range(ch, semitones=12))

    # Program change (skip for drums — channel 9 ignores patch)
    if ch != 9:
        events.append((0, bytes([0xC0 | ch, gm_patch & 0x7F])))

    for note in notes:
        pitch = int(note["pitch"]) & 0x7F
        velocity = max(1, min(127, int(note["velocity"])))
        duration_beats = float(note["duration"])
        tick_on = int(float(note["time"]) * TICKS_PER_BEAT)
        tick_off = int((float(note["time"]) + duration_beats) * TICKS_PER_BEAT)
        tick_off = max(tick_off, tick_on + 1)

        bend_start = note.get("bend_start", 0.0) or 0.0
        bend_end = note.get("bend_end", 0.0) or 0.0
        vibrato_depth = note.get("vibrato", 0.0) or 0.0
        vibrato_delay = note.get("vibrato_delay", 0.25)
        if vibrato_delay is None:
            vibrato_delay = 0.25

        # --- bend_start: slide from bend_start semitones into pitch at tick_on ---
        if bend_start != 0.0:
            glide_beats = min(0.25, duration_beats * 0.3)
            glide_ticks = round(glide_beats * TICKS_PER_BEAT)
            glide_end_tick = tick_on + glide_ticks
            # Initial bend at tick_on, then interpolate back to 0
            events.extend(_interpolate_bend_events(
                ch, tick_on, glide_end_tick, bend_start, 0.0, steps=10
            ))

        # --- vibrato: sine oscillation after delay ---
        if vibrato_depth > 0.0:
            events.extend(_vibrato_events(
                ch, tick_on, tick_off, duration_beats, vibrato_depth, vibrato_delay
            ))

        # --- bend_end: slide from 0 to bend_end at the tail of the note ---
        if bend_end != 0.0:
            glide_beats = min(0.25, duration_beats * 0.3)
            glide_ticks = round(glide_beats * TICKS_PER_BEAT)
            glide_start_tick = tick_off - glide_ticks
            events.extend(_interpolate_bend_events(
                ch, glide_start_tick, tick_off, 0.0, bend_end, steps=10
            ))

        # Note on / note off
        events.append((tick_on, bytes([0x90 | ch, pitch, velocity])))
        events.append((tick_off, bytes([0x80 | ch, pitch, 0x00])))

        # Always reset pitch bend to center at note-off so the next note starts clean
        events.append((tick_off, _pitch_bend_event(ch, 0.0)))

    # Stable sort: note-on events before pitch-bend resets at the same tick
    # We use a secondary key: note-on (0x90) before note-off (0x80) before bend reset
    def event_sort_key(e: Tuple[int, bytes]) -> Tuple[int, int]:
        tick, raw = e
        status = raw[0] if raw else 0xFF
        # Priority within same tick: tempo/meta (0xFF) first, then program (0xC0),
        # then RPN CCs (0xB0), then pitch bend (0xE0) for bend_start,
        # then note-on (0x90), then note-off/bend-reset last
        kind = raw[0] & 0xF0 if raw else 0xFF
        if kind == 0xFF:
            order = 0
        elif kind == 0xC0:
            order = 1
        elif kind == 0xB0:
            order = 2
        elif kind == 0xE0:
            # bend_start bends should come before note-on; bend resets after note-off
            # Differentiate by whether it's a reset (center = 8192 → lsb=0, msb=64)
            lsb = raw[1] if len(raw) > 1 else 0
            msb = raw[2] if len(raw) > 2 else 0
            is_reset = (lsb == 0 and msb == 64)
            order = 6 if is_reset else 3
        elif kind == 0x90:
            order = 4
        elif kind == 0x80:
            order = 5
        else:
            order = 7
        return (tick, order)

    events.sort(key=event_sort_key)

    last_tick = events[-1][0] if events else 0
    if bars is not None:
        eot_tick = bars * 4 * TICKS_PER_BEAT
        eot_tick = max(eot_tick, last_tick + 1)
    else:
        eot_tick = last_tick + TICKS_PER_BEAT * 2
    events.append((eot_tick, bytes([0xFF, 0x2F, 0x00])))

    # Convert absolute ticks → delta-time encoded events
    track_bytes = b""
    current_tick = 0
    for tick, raw in events:
        delta = tick - current_tick
        track_bytes += _encode_vlq(delta) + raw
        current_tick = tick

    return track_bytes


def write_midi(output_path: Path, notes: List[Dict], tempo_bpm: int, gm_patch: int, channel: int = 0, bars: int = None) -> None:
    """Write a MIDI Format 0 file to output_path."""
    track_data = _build_track_data(notes, tempo_bpm, gm_patch, channel, bars=bars)

    # MIDI header chunk
    header = b"MThd"
    header += struct.pack(">I", 6)            # chunk length = 6
    header += struct.pack(">H", 0)            # format 0
    header += struct.pack(">H", 1)            # 1 track
    header += struct.pack(">H", TICKS_PER_BEAT)

    # MIDI track chunk
    track = b"MTrk"
    track += struct.pack(">I", len(track_data))
    track += track_data

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(header + track)
