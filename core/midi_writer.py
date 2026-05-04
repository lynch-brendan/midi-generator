"""
Pure Python MIDI binary writer — no external dependencies.
Writes MIDI Format 0 (single-track) files.
"""
import struct
from pathlib import Path
from typing import List, Dict, Any


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


def _build_track_data(notes: List[Dict], tempo_bpm: int, gm_patch: int, channel: int = 0) -> bytes:
    """
    Build raw MIDI track bytes from a list of note dicts.

    Each note dict must have: pitch, duration (beats), velocity, time (beats).
    Returns the raw event bytes (without the MTrk header/length).
    """
    us_per_beat = int(60_000_000 / max(tempo_bpm, 1))
    events: List[tuple] = []  # (absolute_ticks, raw_event_bytes)

    # Tempo meta event
    tempo_event = bytes([
        0xFF, 0x51, 0x03,
        (us_per_beat >> 16) & 0xFF,
        (us_per_beat >> 8) & 0xFF,
        us_per_beat & 0xFF,
    ])
    events.append((0, tempo_event))

    ch = channel & 0x0F
    # Program change (skip for drums — channel 9 ignores patch)
    if ch != 9:
        events.append((0, bytes([0xC0 | ch, gm_patch & 0x7F])))

    # Note on / note off pairs
    for note in notes:
        pitch = int(note["pitch"]) & 0x7F
        velocity = max(1, min(127, int(note["velocity"])))
        tick_on = int(float(note["time"]) * TICKS_PER_BEAT)
        tick_off = int((float(note["time"]) + float(note["duration"])) * TICKS_PER_BEAT)
        tick_off = max(tick_off, tick_on + 1)

        events.append((tick_on, bytes([0x90 | ch, pitch, velocity])))
        events.append((tick_off, bytes([0x80 | ch, pitch, 0x00])))

    # Sort by time; stable sort preserves note-on before note-off at same tick
    events.sort(key=lambda e: e[0])

    # End-of-track: two beats after the last event
    last_tick = events[-1][0] if events else 0
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


def write_midi(output_path: Path, notes: List[Dict], tempo_bpm: int, gm_patch: int, channel: int = 0) -> None:
    """Write a MIDI Format 0 file to output_path."""
    track_data = _build_track_data(notes, tempo_bpm, gm_patch, channel)

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
