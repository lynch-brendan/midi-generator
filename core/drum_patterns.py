"""
Hardcoded drum pattern skeletons — kick, snare, hi-hats, crash, and fills.
Sources: MusicRadar, Attack Magazine, drum-patterns.com, Jazz Night School, BandLab.

Python controls: kick, snare/clap, hi-hats (CHH/OHH/pedal), crash on phrase starts,
                 and bar-4 fills (tom runs, snare rolls, hat bursts per genre).
Claude controls: ghost notes (vel < 55) only.
Velocity humanization: ±8 random spread applied to every skeleton note at render time.

Public API:
    get_skeleton(genre, bars)          -> List[Dict]
    apply_skeleton(notes, genre, bars) -> List[Dict]
"""
import math
import random
from typing import List, Dict, Optional, Set

_PATTERNS: Dict[str, dict] = {

    # Sources: MusicRadar + UJAM dembow tutorials
    # Four-on-floor kick. Syncopated clap on steps 4,7,12,15.
    # Straight 8th-note hats — no swing, mechanical grid.
    "dembow": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 110, "duration": 0.5},
            {"pitch": 36, "time": 1.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 36, "time": 3.0,  "velocity": 103, "duration": 0.5},
            {"pitch": 39, "time": 0.75, "velocity": 88,  "duration": 0.1},
            {"pitch": 39, "time": 1.5,  "velocity": 100, "duration": 0.1},
            {"pitch": 39, "time": 2.75, "velocity": 82,  "duration": 0.1},
            {"pitch": 39, "time": 3.5,  "velocity": 100, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 82,  "duration": 0.1},
        ],
        "fill": None,
    },

    # Sources: eMastered + MusicRadar trap hi-hat guide + LANDR trap hats
    # Half-time snare on beat 3. 8th-note hats with open hat ON snare.
    # 32nd-note roll before phrase end (bar 2 / fill bar).
    "trap": {
        "bar_length": 2,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "skeleton": [
            # Bar 1: kick, snare, 8th hats, open hat on snare
            {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 0.75, "velocity": 85,  "duration": 0.5},
            {"pitch": 38, "time": 2.0,  "velocity": 118, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 58,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 58,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 52,  "duration": 0.1},
            {"pitch": 46, "time": 2.0,  "velocity": 88,  "duration": 0.5},
            # Bar 2: different kick placement, 32nd roll before end
            {"pitch": 36, "time": 4.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 5.75, "velocity": 78,  "duration": 0.5},
            {"pitch": 38, "time": 6.0,  "velocity": 118, "duration": 0.1},
            {"pitch": 42, "time": 4.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 42, "time": 4.5,  "velocity": 58,  "duration": 0.1},
            {"pitch": 42, "time": 5.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 5.5,  "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 6.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 6.5,  "velocity": 58,  "duration": 0.1},
            {"pitch": 42, "time": 7.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 7.25, "velocity": 42,  "duration": 0.05},
            {"pitch": 42, "time": 7.375,"velocity": 58,  "duration": 0.05},
            {"pitch": 42, "time": 7.5,  "velocity": 72,  "duration": 0.05},
            {"pitch": 42, "time": 7.625,"velocity": 88,  "duration": 0.05},
            {"pitch": 42, "time": 7.75, "velocity": 102, "duration": 0.05},
            {"pitch": 46, "time": 6.0,  "velocity": 88,  "duration": 0.5},
        ],
        "fills": [
            # Variant 1: 32nd hat roll
            [
                {"pitch": 36, "time": 0.0,   "velocity": 112, "duration": 0.5},
                {"pitch": 36, "time": 2.5,   "velocity": 85,  "duration": 0.5},
                {"pitch": 38, "time": 2.0,   "velocity": 118, "duration": 0.1},
                {"pitch": 42, "time": 0.0,   "velocity": 90,  "duration": 0.1},
                {"pitch": 42, "time": 0.5,   "velocity": 58,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,   "velocity": 85,  "duration": 0.1},
                {"pitch": 42, "time": 1.5,   "velocity": 52,  "duration": 0.1},
                {"pitch": 42, "time": 2.0,   "velocity": 80,  "duration": 0.1},
                {"pitch": 42, "time": 2.5,   "velocity": 58,  "duration": 0.1},
                {"pitch": 42, "time": 3.0,   "velocity": 85,  "duration": 0.1},
                {"pitch": 42, "time": 3.25,  "velocity": 40,  "duration": 0.05},
                {"pitch": 42, "time": 3.375, "velocity": 55,  "duration": 0.05},
                {"pitch": 42, "time": 3.5,   "velocity": 70,  "duration": 0.05},
                {"pitch": 42, "time": 3.625, "velocity": 88,  "duration": 0.05},
                {"pitch": 42, "time": 3.75,  "velocity": 105, "duration": 0.05},
                {"pitch": 46, "time": 2.0,   "velocity": 88,  "duration": 0.5},
            ],
            # Variant 2: pull back (silence 3.0-3.375) then hard burst
            [
                {"pitch": 36, "time": 0.0,   "velocity": 112, "duration": 0.5},
                {"pitch": 36, "time": 2.5,   "velocity": 85,  "duration": 0.5},
                {"pitch": 38, "time": 2.0,   "velocity": 118, "duration": 0.1},
                {"pitch": 42, "time": 0.0,   "velocity": 90,  "duration": 0.1},
                {"pitch": 42, "time": 0.5,   "velocity": 58,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,   "velocity": 85,  "duration": 0.1},
                {"pitch": 42, "time": 1.5,   "velocity": 52,  "duration": 0.1},
                {"pitch": 42, "time": 2.0,   "velocity": 80,  "duration": 0.1},
                {"pitch": 42, "time": 2.5,   "velocity": 58,  "duration": 0.1},
                # silence 3.0–3.375, then explosion
                {"pitch": 42, "time": 3.375, "velocity": 52,  "duration": 0.05},
                {"pitch": 42, "time": 3.5,   "velocity": 72,  "duration": 0.05},
                {"pitch": 42, "time": 3.625, "velocity": 92,  "duration": 0.05},
                {"pitch": 42, "time": 3.75,  "velocity": 112, "duration": 0.05},
                {"pitch": 46, "time": 2.0,   "velocity": 88,  "duration": 0.5},
            ],
            # Variant 3: progressive density 8th→16th→32nd
            [
                {"pitch": 36, "time": 0.0,   "velocity": 112, "duration": 0.5},
                {"pitch": 36, "time": 2.5,   "velocity": 85,  "duration": 0.5},
                {"pitch": 38, "time": 2.0,   "velocity": 118, "duration": 0.1},
                {"pitch": 42, "time": 0.0,   "velocity": 85,  "duration": 0.1},
                {"pitch": 42, "time": 0.5,   "velocity": 55,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,   "velocity": 82,  "duration": 0.1},
                {"pitch": 42, "time": 1.5,   "velocity": 52,  "duration": 0.1},
                {"pitch": 42, "time": 2.0,   "velocity": 82,  "duration": 0.1},
                {"pitch": 42, "time": 2.25,  "velocity": 65,  "duration": 0.1},
                {"pitch": 42, "time": 2.5,   "velocity": 75,  "duration": 0.1},
                {"pitch": 42, "time": 2.75,  "velocity": 62,  "duration": 0.1},
                {"pitch": 42, "time": 3.0,   "velocity": 78,  "duration": 0.05},
                {"pitch": 42, "time": 3.125, "velocity": 68,  "duration": 0.05},
                {"pitch": 42, "time": 3.25,  "velocity": 82,  "duration": 0.05},
                {"pitch": 42, "time": 3.375, "velocity": 72,  "duration": 0.05},
                {"pitch": 42, "time": 3.5,   "velocity": 90,  "duration": 0.05},
                {"pitch": 42, "time": 3.625, "velocity": 98,  "duration": 0.05},
                {"pitch": 42, "time": 3.75,  "velocity": 110, "duration": 0.05},
                {"pitch": 46, "time": 2.0,   "velocity": 88,  "duration": 0.5},
            ],
        ],
    },

    # Sources: Attack Magazine 90s Boom Bap + Native Instruments hip-hop patterns
    # Kick on 1+2.5+3 with ghost. Swung 8th hats (+0.05 on offbeats). OHH on "and of 4".
    "boom_bap": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "crash_velocity": 72,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 36, "time": 1.25, "velocity": 52,  "duration": 0.5},
            {"pitch": 36, "time": 1.5,  "velocity": 95,  "duration": 0.5},
            {"pitch": 36, "time": 2.5,  "velocity": 88,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 100, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 100, "duration": 0.1},
            # Swung 8th hats (offbeats pushed +0.05)
            {"pitch": 42, "time": 0.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 0.55, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 1.55, "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 2.55, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 46, "time": 3.55, "velocity": 75,  "duration": 0.5},
        ],
        "fills": [
            # Variant 1: snare roll beat 4
            [
                {"pitch": 36, "time": 0.0,  "velocity": 105, "duration": 0.5},
                {"pitch": 36, "time": 1.25, "velocity": 52,  "duration": 0.5},
                {"pitch": 36, "time": 1.5,  "velocity": 95,  "duration": 0.5},
                {"pitch": 36, "time": 2.5,  "velocity": 88,  "duration": 0.5},
                {"pitch": 38, "time": 1.0,  "velocity": 100, "duration": 0.1},
                {"pitch": 38, "time": 3.0,  "velocity": 78,  "duration": 0.1},
                {"pitch": 38, "time": 3.25, "velocity": 90,  "duration": 0.1},
                {"pitch": 38, "time": 3.5,  "velocity": 100, "duration": 0.1},
                {"pitch": 38, "time": 3.75, "velocity": 112, "duration": 0.1},
                {"pitch": 42, "time": 0.0,  "velocity": 85,  "duration": 0.1},
                {"pitch": 42, "time": 0.55, "velocity": 50,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,  "velocity": 80,  "duration": 0.1},
                {"pitch": 42, "time": 1.55, "velocity": 48,  "duration": 0.1},
                {"pitch": 42, "time": 2.0,  "velocity": 85,  "duration": 0.1},
                {"pitch": 42, "time": 2.55, "velocity": 50,  "duration": 0.1},
            ],
            # Variant 2: high tom + snare alternating (MPC-style)
            [
                {"pitch": 36, "time": 0.0,  "velocity": 105, "duration": 0.5},
                {"pitch": 36, "time": 1.25, "velocity": 52,  "duration": 0.5},
                {"pitch": 36, "time": 1.5,  "velocity": 95,  "duration": 0.5},
                {"pitch": 36, "time": 2.5,  "velocity": 88,  "duration": 0.5},
                {"pitch": 38, "time": 1.0,  "velocity": 100, "duration": 0.1},
                {"pitch": 50, "time": 3.0,  "velocity": 90,  "duration": 0.1},
                {"pitch": 38, "time": 3.25, "velocity": 80,  "duration": 0.1},
                {"pitch": 50, "time": 3.5,  "velocity": 85,  "duration": 0.1},
                {"pitch": 38, "time": 3.75, "velocity": 108, "duration": 0.1},
                {"pitch": 42, "time": 0.0,  "velocity": 85,  "duration": 0.1},
                {"pitch": 42, "time": 0.55, "velocity": 50,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,  "velocity": 80,  "duration": 0.1},
                {"pitch": 42, "time": 1.55, "velocity": 48,  "duration": 0.1},
                {"pitch": 42, "time": 2.0,  "velocity": 85,  "duration": 0.1},
                {"pitch": 42, "time": 2.55, "velocity": 50,  "duration": 0.1},
                {"pitch": 46, "time": 3.55, "velocity": 78,  "duration": 0.4},
            ],
        ],
    },

    # Sources: Attack Magazine Chicago House + BandLab house tutorial
    # Four-on-floor + clap on 2+4. CHH on beats, OHH on every offbeat (jacking pattern).
    "house": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": True,
        "crash_velocity": 88,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 115, "duration": 0.5},
            {"pitch": 36, "time": 1.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 115, "duration": 0.5},
            {"pitch": 36, "time": 3.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 39, "time": 1.0,  "velocity": 102, "duration": 0.1},
            {"pitch": 39, "time": 3.0,  "velocity": 102, "duration": 0.1},
            # CHH on beats (quarter notes)
            {"pitch": 42, "time": 0.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 75,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 75,  "duration": 0.1},
            # OHH on every offbeat — the jacking house pattern
            {"pitch": 46, "time": 0.5,  "velocity": 95,  "duration": 0.4},
            {"pitch": 46, "time": 1.5,  "velocity": 92,  "duration": 0.4},
            {"pitch": 46, "time": 2.5,  "velocity": 95,  "duration": 0.4},
            {"pitch": 46, "time": 3.5,  "velocity": 92,  "duration": 0.4},
        ],
        "fill": None,
    },

    # Sources: DrumsTheWord Funky Drummer lesson + MusicRadar MIDI breakdown
    # Syncopated kick. All 16th hats. OHH on "e of beats 2+4" (Clyde Stubblefield position).
    "funk": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "crash_velocity": 88,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 110, "duration": 0.5},
            {"pitch": 36, "time": 0.5,  "velocity": 82,  "duration": 0.5},
            {"pitch": 36, "time": 1.25, "velocity": 70,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 100, "duration": 0.5},
            {"pitch": 36, "time": 3.0,  "velocity": 88,  "duration": 0.5},
            {"pitch": 36, "time": 3.75, "velocity": 85,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 108, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 108, "duration": 0.1},
            # All 16th hats, minus the OHH positions (1.25 and 3.25)
            {"pitch": 42, "time": 0.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 42, "time": 0.25, "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 75,  "duration": 0.1},
            {"pitch": 42, "time": 0.75, "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 92,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 75,  "duration": 0.1},
            {"pitch": 42, "time": 1.75, "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 42, "time": 2.25, "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 75,  "duration": 0.1},
            {"pitch": 42, "time": 2.75, "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 92,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 75,  "duration": 0.1},
            {"pitch": 42, "time": 3.75, "velocity": 48,  "duration": 0.1},
            # OHH on "e" of beats 2 and 4 — the Funky Drummer signature
            {"pitch": 46, "time": 1.25, "velocity": 85,  "duration": 0.25},
            {"pitch": 46, "time": 3.25, "velocity": 85,  "duration": 0.25},
        ],
        "fills": [
            # Variant 1: tom descent beat 4
            [
                {"pitch": 36, "time": 0.0,  "velocity": 110, "duration": 0.5},
                {"pitch": 36, "time": 0.5,  "velocity": 82,  "duration": 0.5},
                {"pitch": 36, "time": 1.25, "velocity": 70,  "duration": 0.5},
                {"pitch": 36, "time": 2.0,  "velocity": 100, "duration": 0.5},
                {"pitch": 38, "time": 1.0,  "velocity": 108, "duration": 0.1},
                {"pitch": 42, "time": 0.0,  "velocity": 95,  "duration": 0.1},
                {"pitch": 42, "time": 0.25, "velocity": 52,  "duration": 0.1},
                {"pitch": 42, "time": 0.5,  "velocity": 75,  "duration": 0.1},
                {"pitch": 42, "time": 0.75, "velocity": 48,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,  "velocity": 92,  "duration": 0.1},
                {"pitch": 42, "time": 1.5,  "velocity": 75,  "duration": 0.1},
                {"pitch": 42, "time": 1.75, "velocity": 48,  "duration": 0.1},
                {"pitch": 42, "time": 2.0,  "velocity": 95,  "duration": 0.1},
                {"pitch": 42, "time": 2.25, "velocity": 52,  "duration": 0.1},
                {"pitch": 42, "time": 2.5,  "velocity": 75,  "duration": 0.1},
                {"pitch": 42, "time": 2.75, "velocity": 48,  "duration": 0.1},
                {"pitch": 46, "time": 1.25, "velocity": 85,  "duration": 0.25},
                {"pitch": 50, "time": 3.0,  "velocity": 95,  "duration": 0.1},
                {"pitch": 38, "time": 3.25, "velocity": 88,  "duration": 0.1},
                {"pitch": 48, "time": 3.5,  "velocity": 92,  "duration": 0.1},
                {"pitch": 45, "time": 3.75, "velocity": 88,  "duration": 0.1},
            ],
            # Variant 2: snare triplet flam run beat 4
            [
                {"pitch": 36, "time": 0.0,  "velocity": 110, "duration": 0.5},
                {"pitch": 36, "time": 0.5,  "velocity": 82,  "duration": 0.5},
                {"pitch": 36, "time": 1.25, "velocity": 70,  "duration": 0.5},
                {"pitch": 36, "time": 2.0,  "velocity": 100, "duration": 0.5},
                {"pitch": 38, "time": 1.0,  "velocity": 108, "duration": 0.1},
                {"pitch": 42, "time": 0.0,  "velocity": 95,  "duration": 0.1},
                {"pitch": 42, "time": 0.25, "velocity": 52,  "duration": 0.1},
                {"pitch": 42, "time": 0.5,  "velocity": 75,  "duration": 0.1},
                {"pitch": 42, "time": 0.75, "velocity": 48,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,  "velocity": 92,  "duration": 0.1},
                {"pitch": 42, "time": 1.5,  "velocity": 75,  "duration": 0.1},
                {"pitch": 42, "time": 1.75, "velocity": 48,  "duration": 0.1},
                {"pitch": 42, "time": 2.0,  "velocity": 95,  "duration": 0.1},
                {"pitch": 42, "time": 2.25, "velocity": 52,  "duration": 0.1},
                {"pitch": 42, "time": 2.5,  "velocity": 75,  "duration": 0.1},
                {"pitch": 42, "time": 2.75, "velocity": 48,  "duration": 0.1},
                {"pitch": 46, "time": 1.25, "velocity": 85,  "duration": 0.25},
                # Triplet snare run (6 hits as 8th triplets)
                {"pitch": 38, "time": 3.0,  "velocity": 88,  "duration": 0.1},
                {"pitch": 38, "time": 3.17, "velocity": 72,  "duration": 0.1},
                {"pitch": 38, "time": 3.33, "velocity": 95,  "duration": 0.1},
                {"pitch": 38, "time": 3.5,  "velocity": 78,  "duration": 0.1},
                {"pitch": 38, "time": 3.67, "velocity": 98,  "duration": 0.1},
                {"pitch": 38, "time": 3.83, "velocity": 108, "duration": 0.1},
            ],
            # Variant 3: breakdown — drop hats entirely, just kick+snare (tension before crash)
            [
                {"pitch": 36, "time": 0.0,  "velocity": 115, "duration": 0.5},
                {"pitch": 36, "time": 0.5,  "velocity": 88,  "duration": 0.5},
                {"pitch": 36, "time": 1.25, "velocity": 75,  "duration": 0.5},
                {"pitch": 36, "time": 2.0,  "velocity": 108, "duration": 0.5},
                {"pitch": 36, "time": 3.0,  "velocity": 98,  "duration": 0.5},
                {"pitch": 38, "time": 1.0,  "velocity": 118, "duration": 0.1},
                {"pitch": 38, "time": 3.0,  "velocity": 118, "duration": 0.1},
                # no hats — the silence IS the fill
            ],
        ],
    },

    # Sources: Jazz Night School + drumhelper.com + Paul Wertico ride pattern
    # Feathered kick on 1+3. Pedal HH on 2+4. Ride spang-a-lang (triplet swing).
    # No closed hat — ride carries time.
    "jazz_swing": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 41, 43, 44, 45, 47, 48, 49, 50, 51},
        "crash_on_phrase_start": False,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 32,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 28,  "duration": 0.5},
            {"pitch": 44, "time": 1.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 44, "time": 3.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 51, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 0.67, "velocity": 62,  "duration": 0.1},
            {"pitch": 51, "time": 1.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 1.67, "velocity": 62,  "duration": 0.1},
            {"pitch": 51, "time": 2.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 2.67, "velocity": 62,  "duration": 0.1},
            {"pitch": 51, "time": 3.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 3.67, "velocity": 62,  "duration": 0.1},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,  "velocity": 32,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 28,  "duration": 0.5},
            {"pitch": 44, "time": 1.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 44, "time": 3.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 51, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 0.67, "velocity": 62,  "duration": 0.1},
            {"pitch": 51, "time": 1.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 1.67, "velocity": 62,  "duration": 0.1},
            {"pitch": 51, "time": 2.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 2.67, "velocity": 62,  "duration": 0.1},
            # Light conversational fill on beat 4
            {"pitch": 50, "time": 3.0,  "velocity": 78,  "duration": 0.1},
            {"pitch": 38, "time": 3.33, "velocity": 82,  "duration": 0.1},
            {"pitch": 50, "time": 3.67, "velocity": 72,  "duration": 0.1},
        ],
    },

    # Sources: Wikipedia one-drop + MusicRadar reggae MIDI programming guide
    # ONE-DROP: kick + cross-stick on beat 3 ONLY. Hats on upbeats only (no downbeats).
    "reggae": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 37, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "skeleton": [
            {"pitch": 36, "time": 2.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 37, "time": 2.0,  "velocity": 100, "duration": 0.1},
            # Upbeats only — no hats on downbeats
            {"pitch": 42, "time": 0.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 75,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 78,  "duration": 0.1},
            # OHH: "and of 4" — floats into next bar
            {"pitch": 46, "time": 3.5,  "velocity": 82,  "duration": 0.4},
        ],
        "fill": [
            {"pitch": 36, "time": 2.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 37, "time": 2.0,  "velocity": 100, "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 75,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 78,  "duration": 0.1},
            # Triplet hat fill into bar end
            {"pitch": 42, "time": 3.0,  "velocity": 65,  "duration": 0.1},
            {"pitch": 42, "time": 3.33, "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 3.67, "velocity": 90,  "duration": 0.1},
            {"pitch": 37, "time": 3.75, "velocity": 92,  "duration": 0.1},
        ],
    },

    # Sources: Sweetwater iconic fills + drumhelper.com rock beats
    # Kick 1+3, snare 2+4. Steady 8th hats. Crash on phrase start and after fill.
    "rock": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": True,
        "crash_velocity": 108,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 115, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 115, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 70,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 92,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 70,  "duration": 0.1},
        ],
        "fills": [
            # Variant 1: 8th-note descending tom run (Bonham style)
            [
                {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
                {"pitch": 36, "time": 2.0,  "velocity": 108, "duration": 0.5},
                {"pitch": 50, "time": 0.0,  "velocity": 95,  "duration": 0.1},
                {"pitch": 50, "time": 0.5,  "velocity": 90,  "duration": 0.1},
                {"pitch": 38, "time": 1.0,  "velocity": 100, "duration": 0.1},
                {"pitch": 38, "time": 1.5,  "velocity": 95,  "duration": 0.1},
                {"pitch": 48, "time": 2.0,  "velocity": 92,  "duration": 0.1},
                {"pitch": 48, "time": 2.5,  "velocity": 88,  "duration": 0.1},
                {"pitch": 45, "time": 3.0,  "velocity": 90,  "duration": 0.1},
                {"pitch": 41, "time": 3.5,  "velocity": 88,  "duration": 0.1},
            ],
            # Variant 2: 16th snare roll + floor tom landing
            [
                {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
                {"pitch": 36, "time": 2.0,  "velocity": 108, "duration": 0.5},
                {"pitch": 42, "time": 0.0,  "velocity": 90,  "duration": 0.1},
                {"pitch": 42, "time": 0.5,  "velocity": 72,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,  "velocity": 88,  "duration": 0.1},
                {"pitch": 42, "time": 1.5,  "velocity": 70,  "duration": 0.1},
                {"pitch": 38, "time": 2.0,  "velocity": 85,  "duration": 0.1},
                {"pitch": 38, "time": 2.25, "velocity": 78,  "duration": 0.1},
                {"pitch": 38, "time": 2.5,  "velocity": 88,  "duration": 0.1},
                {"pitch": 38, "time": 2.75, "velocity": 82,  "duration": 0.1},
                {"pitch": 38, "time": 3.0,  "velocity": 92,  "duration": 0.1},
                {"pitch": 38, "time": 3.25, "velocity": 88,  "duration": 0.1},
                {"pitch": 38, "time": 3.5,  "velocity": 100, "duration": 0.1},
                {"pitch": 41, "time": 3.75, "velocity": 108, "duration": 0.1},
            ],
            # Variant 3: mini fill — just beat 4 (4× 16th toms)
            [
                {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
                {"pitch": 36, "time": 2.0,  "velocity": 108, "duration": 0.5},
                {"pitch": 38, "time": 1.0,  "velocity": 115, "duration": 0.1},
                {"pitch": 42, "time": 0.0,  "velocity": 90,  "duration": 0.1},
                {"pitch": 42, "time": 0.5,  "velocity": 72,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,  "velocity": 88,  "duration": 0.1},
                {"pitch": 42, "time": 1.5,  "velocity": 70,  "duration": 0.1},
                {"pitch": 42, "time": 2.0,  "velocity": 92,  "duration": 0.1},
                {"pitch": 42, "time": 2.5,  "velocity": 72,  "duration": 0.1},
                {"pitch": 42, "time": 3.0,  "velocity": 88,  "duration": 0.1},
                {"pitch": 50, "time": 3.0,  "velocity": 95,  "duration": 0.1},
                {"pitch": 38, "time": 3.25, "velocity": 90,  "duration": 0.1},
                {"pitch": 48, "time": 3.5,  "velocity": 92,  "duration": 0.1},
                {"pitch": 41, "time": 3.75, "velocity": 95,  "duration": 0.1},
            ],
        ],
    },

    # Sources: joethedrummer.com Afrobeat + samplefocus Afrobeats blog
    # Dense 16th hats. Cross-stick on "and of 1" and "and of 3" (talking drum feel).
    # OHH at same positions for lift.
    "afrobeats": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 37, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 100, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 100, "duration": 0.1},
            {"pitch": 37, "time": 0.5,  "velocity": 85,  "duration": 0.1},
            {"pitch": 37, "time": 2.5,  "velocity": 85,  "duration": 0.1},
            # 16th hats (skipping 0.5 and 2.5 — replaced by OHH)
            {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 0.25, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 0.75, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 1.25, "velocity": 58,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 1.75, "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 2.25, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 2.75, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 3.25, "velocity": 58,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 3.75, "velocity": 52,  "duration": 0.1},
            {"pitch": 46, "time": 0.5,  "velocity": 78,  "duration": 0.2},
            {"pitch": 46, "time": 2.5,  "velocity": 78,  "duration": 0.2},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 100, "duration": 0.1},
            {"pitch": 37, "time": 0.5,  "velocity": 85,  "duration": 0.1},
            {"pitch": 37, "time": 2.5,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 0.25, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 0.75, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 1.25, "velocity": 58,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 1.75, "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 2.25, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 2.75, "velocity": 55,  "duration": 0.1},
            {"pitch": 46, "time": 0.5,  "velocity": 78,  "duration": 0.2},
            {"pitch": 46, "time": 2.5,  "velocity": 78,  "duration": 0.2},
            # Beat 4: syncopated snare/cross-stick burst
            {"pitch": 38, "time": 3.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 37, "time": 3.25, "velocity": 90,  "duration": 0.1},
            {"pitch": 38, "time": 3.5,  "velocity": 98,  "duration": 0.1},
            {"pitch": 37, "time": 3.75, "velocity": 105, "duration": 0.1},
        ],
    },

    # Sources: Attack Magazine UK Drill + BandLab UK drill tutorial
    # Grime-derived tresillo hat (2-2-1): steps 1,4,7,9,12,15.
    # 32nd hat roll before phrase end. No crash.
    "uk_drill": {
        "bar_length": 2,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 3.5,  "velocity": 90,  "duration": 0.5},
            {"pitch": 38, "time": 2.0,  "velocity": 118, "duration": 0.1},
            {"pitch": 36, "time": 4.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 5.0,  "velocity": 88,  "duration": 0.5},
            {"pitch": 38, "time": 6.0,  "velocity": 118, "duration": 0.1},
            {"pitch": 38, "time": 6.75, "velocity": 90,  "duration": 0.1},
            # Tresillo hat bar 1: 0, 0.75, 1.5, 2.0, 2.75, 3.5
            {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 0.75, "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 2.75, "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 85,  "duration": 0.1},
            # Tresillo hat bar 2 + 32nd roll before end
            {"pitch": 42, "time": 4.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 4.75, "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 5.5,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 6.0,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 6.75, "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 7.25, "velocity": 40,  "duration": 0.05},
            {"pitch": 42, "time": 7.375,"velocity": 58,  "duration": 0.05},
            {"pitch": 42, "time": 7.5,  "velocity": 72,  "duration": 0.05},
            {"pitch": 42, "time": 7.625,"velocity": 88,  "duration": 0.05},
            {"pitch": 42, "time": 7.75, "velocity": 102, "duration": 0.05},
        ],
        "fill": None,
    },

    # Lo-fi hip-hop: deeper swing than boom bap (+0.1 on offbeats = Dilla feel).
    # OHH on swung "and of 2" and "and of 4". No crash (dusty, worn-in aesthetic).
    "lofi": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 100, "duration": 0.5},
            {"pitch": 36, "time": 1.5,  "velocity": 88,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 95,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 90,  "duration": 0.1},
            # Swung 8th hats (offbeats +0.1 for Dilla feel)
            {"pitch": 42, "time": 0.0,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 0.6,  "velocity": 44,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 68,  "duration": 0.1},
            {"pitch": 42, "time": 1.6,  "velocity": 42,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 2.6,  "velocity": 44,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 68,  "duration": 0.1},
            # OHH on swung offbeats of beats 2 and 4
            {"pitch": 46, "time": 1.6,  "velocity": 65,  "duration": 0.4},
            {"pitch": 46, "time": 3.6,  "velocity": 62,  "duration": 0.4},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,  "velocity": 100, "duration": 0.5},
            {"pitch": 36, "time": 1.5,  "velocity": 88,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 95,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 0.6,  "velocity": 44,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 68,  "duration": 0.1},
            {"pitch": 42, "time": 1.6,  "velocity": 42,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 2.6,  "velocity": 44,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 68,  "duration": 0.1},
            {"pitch": 46, "time": 1.6,  "velocity": 65,  "duration": 0.4},
            # Light snare roll on beat 4
            {"pitch": 38, "time": 3.25, "velocity": 72,  "duration": 0.1},
            {"pitch": 38, "time": 3.5,  "velocity": 82,  "duration": 0.1},
            {"pitch": 38, "time": 3.75, "velocity": 92,  "duration": 0.1},
        ],
    },

    # Sources: drum-patterns.com/bossa-nova-1 + Brad Allen Drums bossa nova lesson
    # 3-2 son clave on rimshot. Kick on steps 1,7,9,15. Featherlight 8th hats (vel 45-55).
    "bossa_nova": {
        "bar_length": 2,
        "controlled_pitches": {35, 36, 37, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 85, "duration": 0.5},
            {"pitch": 36, "time": 1.5,  "velocity": 78, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 82, "duration": 0.5},
            {"pitch": 36, "time": 3.5,  "velocity": 75, "duration": 0.5},
            {"pitch": 36, "time": 4.0,  "velocity": 85, "duration": 0.5},
            {"pitch": 36, "time": 5.5,  "velocity": 78, "duration": 0.5},
            {"pitch": 36, "time": 6.0,  "velocity": 82, "duration": 0.5},
            {"pitch": 36, "time": 7.5,  "velocity": 75, "duration": 0.5},
            # 3-2 clave: bar 1 on 1,7,13 / bar 2 on 5,11
            {"pitch": 37, "time": 0.0,  "velocity": 90, "duration": 0.1},
            {"pitch": 37, "time": 1.5,  "velocity": 85, "duration": 0.1},
            {"pitch": 37, "time": 3.0,  "velocity": 90, "duration": 0.1},
            {"pitch": 37, "time": 5.0,  "velocity": 90, "duration": 0.1},
            {"pitch": 37, "time": 6.5,  "velocity": 85, "duration": 0.1},
            # Featherlight 8th hats (very low velocity)
            {"pitch": 42, "time": 0.0,  "velocity": 52, "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 44, "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 52, "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 44, "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 52, "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 44, "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 52, "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 44, "duration": 0.1},
            {"pitch": 42, "time": 4.0,  "velocity": 52, "duration": 0.1},
            {"pitch": 42, "time": 4.5,  "velocity": 44, "duration": 0.1},
            {"pitch": 42, "time": 5.0,  "velocity": 52, "duration": 0.1},
            {"pitch": 42, "time": 5.5,  "velocity": 44, "duration": 0.1},
            {"pitch": 42, "time": 6.0,  "velocity": 52, "duration": 0.1},
            {"pitch": 42, "time": 6.5,  "velocity": 44, "duration": 0.1},
            {"pitch": 42, "time": 7.0,  "velocity": 52, "duration": 0.1},
            {"pitch": 42, "time": 7.5,  "velocity": 44, "duration": 0.1},
        ],
        "fill": None,
    },

    # Half-time / neo-soul: snare on beat 3 only. Triplet hats (12 per bar).
    # OHH with snare. Dense ghost-heavy tom fill.
    "halftime": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": True,
        "crash_velocity": 92,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 38, "time": 2.0,  "velocity": 118, "duration": 0.1},
            # 8th-note triplet hats (12 per bar)
            {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 0.33, "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 0.67, "velocity": 70,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 1.33, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 1.67, "velocity": 68,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 2.33, "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 2.67, "velocity": 70,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 3.33, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 3.67, "velocity": 68,  "duration": 0.1},
            {"pitch": 46, "time": 2.0,  "velocity": 88,  "duration": 0.5},
        ],
        "fills": [
            # Variant 1: ghost-heavy tom tumble (Anderson .Paak style)
            [
                {"pitch": 36, "time": 0.0,  "velocity": 108, "duration": 0.5},
                {"pitch": 38, "time": 2.0,  "velocity": 118, "duration": 0.1},
                {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
                {"pitch": 42, "time": 0.33, "velocity": 52,  "duration": 0.1},
                {"pitch": 42, "time": 0.67, "velocity": 70,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,  "velocity": 85,  "duration": 0.1},
                {"pitch": 42, "time": 1.33, "velocity": 50,  "duration": 0.1},
                {"pitch": 42, "time": 1.67, "velocity": 68,  "duration": 0.1},
                {"pitch": 46, "time": 2.0,  "velocity": 88,  "duration": 0.5},
                {"pitch": 38, "time": 2.25, "velocity": 38,  "duration": 0.1},
                {"pitch": 50, "time": 2.5,  "velocity": 85,  "duration": 0.1},
                {"pitch": 38, "time": 2.75, "velocity": 35,  "duration": 0.1},
                {"pitch": 48, "time": 3.0,  "velocity": 90,  "duration": 0.1},
                {"pitch": 38, "time": 3.25, "velocity": 40,  "duration": 0.1},
                {"pitch": 45, "time": 3.5,  "velocity": 88,  "duration": 0.1},
                {"pitch": 38, "time": 3.75, "velocity": 98,  "duration": 0.1},
            ],
            # Variant 2: snare roll swell into crash
            [
                {"pitch": 36, "time": 0.0,  "velocity": 108, "duration": 0.5},
                {"pitch": 38, "time": 2.0,  "velocity": 118, "duration": 0.1},
                {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
                {"pitch": 42, "time": 0.33, "velocity": 52,  "duration": 0.1},
                {"pitch": 42, "time": 0.67, "velocity": 70,  "duration": 0.1},
                {"pitch": 42, "time": 1.0,  "velocity": 85,  "duration": 0.1},
                {"pitch": 42, "time": 1.33, "velocity": 50,  "duration": 0.1},
                {"pitch": 42, "time": 1.67, "velocity": 68,  "duration": 0.1},
                {"pitch": 46, "time": 2.0,  "velocity": 88,  "duration": 0.5},
                # Snare roll swell beats 3-4
                {"pitch": 38, "time": 2.25, "velocity": 48,  "duration": 0.1},
                {"pitch": 38, "time": 2.5,  "velocity": 55,  "duration": 0.1},
                {"pitch": 38, "time": 2.75, "velocity": 62,  "duration": 0.1},
                {"pitch": 38, "time": 3.0,  "velocity": 72,  "duration": 0.1},
                {"pitch": 38, "time": 3.25, "velocity": 82,  "duration": 0.1},
                {"pitch": 38, "time": 3.5,  "velocity": 95,  "duration": 0.1},
                {"pitch": 38, "time": 3.75, "velocity": 110, "duration": 0.1},
            ],
        ],
    },

    "default": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "crash_velocity": 88,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 100, "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 105, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 105, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 68,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 65,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 68,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 65,  "duration": 0.1},
        ],
        "fill": None,
    },

    # ── TRAP VARIANTS ─────────────────────────────────────────────────────────

    # Ultra-minimal: kick only beat 1, snare beat 3. Spacious.
    "trap_minimal": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 115, "duration": 0.5},
            {"pitch": 38, "time": 2.0,  "velocity": 120, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 48,  "duration": 0.1},
            {"pitch": 46, "time": 2.0,  "velocity": 92,  "duration": 0.5},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,   "velocity": 115, "duration": 0.5},
            {"pitch": 38, "time": 2.0,   "velocity": 120, "duration": 0.1},
            {"pitch": 42, "time": 0.0,   "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,   "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,   "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,   "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,   "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,   "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,   "velocity": 80,  "duration": 0.1},
            {"pitch": 42, "time": 3.25,  "velocity": 40,  "duration": 0.05},
            {"pitch": 42, "time": 3.375, "velocity": 55,  "duration": 0.05},
            {"pitch": 42, "time": 3.5,   "velocity": 70,  "duration": 0.05},
            {"pitch": 42, "time": 3.625, "velocity": 88,  "duration": 0.05},
            {"pitch": 42, "time": 3.75,  "velocity": 105, "duration": 0.05},
            {"pitch": 46, "time": 2.0,   "velocity": 92,  "duration": 0.5},
        ],
    },

    # Dense: busier kick, 16th-note hat grid, more energetic
    "trap_busy": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 0.75, "velocity": 80,  "duration": 0.5},
            {"pitch": 36, "time": 2.5,  "velocity": 88,  "duration": 0.5},
            {"pitch": 36, "time": 3.25, "velocity": 72,  "duration": 0.5},
            {"pitch": 38, "time": 2.0,  "velocity": 118, "duration": 0.1},
            # 16th-note hats
            {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 0.25, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 75,  "duration": 0.1},
            {"pitch": 42, "time": 0.75, "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 1.25, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 1.75, "velocity": 45,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 2.25, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 2.75, "velocity": 45,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 3.25, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 3.75, "velocity": 45,  "duration": 0.1},
            {"pitch": 46, "time": 2.0,  "velocity": 88,  "duration": 0.5},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,   "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 0.75,  "velocity": 80,  "duration": 0.5},
            {"pitch": 36, "time": 2.5,   "velocity": 88,  "duration": 0.5},
            {"pitch": 38, "time": 2.0,   "velocity": 118, "duration": 0.1},
            {"pitch": 42, "time": 0.0,   "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 0.25,  "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,   "velocity": 75,  "duration": 0.1},
            {"pitch": 42, "time": 0.75,  "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,   "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 1.25,  "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,   "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 1.75,  "velocity": 45,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,   "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,   "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,   "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 3.25,  "velocity": 42,  "duration": 0.05},
            {"pitch": 42, "time": 3.375, "velocity": 58,  "duration": 0.05},
            {"pitch": 42, "time": 3.5,   "velocity": 72,  "duration": 0.05},
            {"pitch": 42, "time": 3.625, "velocity": 90,  "duration": 0.05},
            {"pitch": 42, "time": 3.75,  "velocity": 108, "duration": 0.05},
            {"pitch": 46, "time": 2.0,   "velocity": 88,  "duration": 0.5},
        ],
    },

    # ── BOOM BAP VARIANTS ─────────────────────────────────────────────────────

    # Heavy NYC feel: extra kick anticipation before beat 2 + more syncopation
    "boom_bap_heavy": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "crash_velocity": 78,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 36, "time": 0.75, "velocity": 58,  "duration": 0.5},
            {"pitch": 36, "time": 1.5,  "velocity": 98,  "duration": 0.5},
            {"pitch": 36, "time": 2.5,  "velocity": 90,  "duration": 0.5},
            {"pitch": 36, "time": 3.5,  "velocity": 62,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 105, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 105, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 0.55, "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 1.55, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 2.55, "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 82,  "duration": 0.1},
            {"pitch": 46, "time": 3.55, "velocity": 80,  "duration": 0.5},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 36, "time": 0.75, "velocity": 58,  "duration": 0.5},
            {"pitch": 36, "time": 1.5,  "velocity": 98,  "duration": 0.5},
            {"pitch": 36, "time": 2.5,  "velocity": 90,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 105, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 82,  "duration": 0.1},
            {"pitch": 38, "time": 3.25, "velocity": 92,  "duration": 0.1},
            {"pitch": 38, "time": 3.5,  "velocity": 102, "duration": 0.1},
            {"pitch": 38, "time": 3.75, "velocity": 115, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 0.55, "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 82,  "duration": 0.1},
            {"pitch": 42, "time": 1.55, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 2.55, "velocity": 52,  "duration": 0.1},
        ],
    },

    # Chill / west coast: simpler kick, more relaxed swing
    "boom_bap_chill": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "crash_velocity": 65,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 100, "duration": 0.5},
            {"pitch": 36, "time": 2.5,  "velocity": 92,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 0.55, "velocity": 45,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 1.55, "velocity": 42,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 2.55, "velocity": 45,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 72,  "duration": 0.1},
            {"pitch": 46, "time": 3.55, "velocity": 68,  "duration": 0.5},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,  "velocity": 100, "duration": 0.5},
            {"pitch": 36, "time": 2.5,  "velocity": 92,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 72,  "duration": 0.1},
            {"pitch": 38, "time": 3.25, "velocity": 82,  "duration": 0.1},
            {"pitch": 38, "time": 3.5,  "velocity": 92,  "duration": 0.1},
            {"pitch": 38, "time": 3.75, "velocity": 105, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 0.55, "velocity": 45,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 1.55, "velocity": 42,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 2.55, "velocity": 45,  "duration": 0.1},
        ],
    },

    # ── ROCK VARIANTS ─────────────────────────────────────────────────────────

    # Driving: kick on all 4 beats (AC/DC style)
    "rock_driving": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": True,
        "crash_velocity": 110,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 115, "duration": 0.5},
            {"pitch": 36, "time": 1.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 3.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 118, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 118, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 92,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 74,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 92,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 74,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 72,  "duration": 0.1},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,  "velocity": 115, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 50, "time": 0.0,  "velocity": 98,  "duration": 0.1},
            {"pitch": 50, "time": 0.5,  "velocity": 92,  "duration": 0.1},
            {"pitch": 38, "time": 1.0,  "velocity": 105, "duration": 0.1},
            {"pitch": 38, "time": 1.5,  "velocity": 98,  "duration": 0.1},
            {"pitch": 48, "time": 2.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 48, "time": 2.5,  "velocity": 90,  "duration": 0.1},
            {"pitch": 45, "time": 3.0,  "velocity": 92,  "duration": 0.1},
            {"pitch": 41, "time": 3.5,  "velocity": 90,  "duration": 0.1},
        ],
    },

    # Half-time rock: snare only on beat 3, heavier feel
    "rock_halftime": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": True,
        "crash_velocity": 108,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 115, "duration": 0.5},
            {"pitch": 36, "time": 1.5,  "velocity": 88,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 38, "time": 2.0,  "velocity": 122, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 70,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 70,  "duration": 0.1},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,  "velocity": 115, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 50, "time": 0.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 50, "time": 0.5,  "velocity": 90,  "duration": 0.1},
            {"pitch": 38, "time": 1.0,  "velocity": 100, "duration": 0.1},
            {"pitch": 38, "time": 1.5,  "velocity": 95,  "duration": 0.1},
            {"pitch": 48, "time": 2.0,  "velocity": 92,  "duration": 0.1},
            {"pitch": 48, "time": 2.5,  "velocity": 88,  "duration": 0.1},
            {"pitch": 45, "time": 3.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 41, "time": 3.5,  "velocity": 88,  "duration": 0.1},
        ],
    },

    # ── HOUSE VARIANTS ────────────────────────────────────────────────────────

    # Deep house: sparse open hats, more hypnotic
    "house_deep": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": True,
        "crash_velocity": 82,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 1.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 3.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 39, "time": 1.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 39, "time": 3.0,  "velocity": 95,  "duration": 0.1},
            # 16th CHH on downbeats only — more spacious
            {"pitch": 42, "time": 0.0,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 0.25, "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 1.25, "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 2.25, "velocity": 48,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 72,  "duration": 0.1},
            {"pitch": 42, "time": 3.25, "velocity": 48,  "duration": 0.1},
            # OHH only on "and of 2" and "and of 4"
            {"pitch": 46, "time": 1.5,  "velocity": 88,  "duration": 0.4},
            {"pitch": 46, "time": 3.5,  "velocity": 85,  "duration": 0.4},
        ],
        "fill": None,
    },

    # ── FUNK VARIANTS ─────────────────────────────────────────────────────────

    # Heavy groove: simpler kick, massive backbeat, more room for ghost notes
    "funk_heavy": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "crash_velocity": 90,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 36, "time": 3.0,  "velocity": 90,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 115, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 115, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 98,  "duration": 0.1},
            {"pitch": 42, "time": 0.25, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 0.75, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 1.75, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 98,  "duration": 0.1},
            {"pitch": 42, "time": 2.25, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 2.75, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 42, "time": 3.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 3.75, "velocity": 50,  "duration": 0.1},
            {"pitch": 46, "time": 1.25, "velocity": 90,  "duration": 0.25},
            {"pitch": 46, "time": 3.25, "velocity": 90,  "duration": 0.25},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 115, "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 98,  "duration": 0.1},
            {"pitch": 42, "time": 0.25, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 0.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 0.75, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 42, "time": 1.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 1.75, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 98,  "duration": 0.1},
            {"pitch": 42, "time": 2.25, "velocity": 55,  "duration": 0.1},
            {"pitch": 42, "time": 2.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 42, "time": 2.75, "velocity": 50,  "duration": 0.1},
            {"pitch": 46, "time": 1.25, "velocity": 90,  "duration": 0.25},
            {"pitch": 50, "time": 3.0,  "velocity": 100, "duration": 0.1},
            {"pitch": 38, "time": 3.25, "velocity": 92,  "duration": 0.1},
            {"pitch": 48, "time": 3.5,  "velocity": 95,  "duration": 0.1},
            {"pitch": 45, "time": 3.75, "velocity": 90,  "duration": 0.1},
        ],
    },

    # ── LOFI VARIANTS ─────────────────────────────────────────────────────────

    # Lazy / Nujabes style: sparser, even more swung
    "lofi_lazy": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 41, 43, 45, 47, 48, 50, 42, 44, 46, 49},
        "crash_on_phrase_start": False,
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 95,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 88,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 85,  "duration": 0.1},
            # Very swung 8th hats (offbeats at +0.15 = Dilla maximum)
            {"pitch": 42, "time": 0.0,  "velocity": 68,  "duration": 0.1},
            {"pitch": 42, "time": 0.65, "velocity": 40,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 62,  "duration": 0.1},
            {"pitch": 42, "time": 1.65, "velocity": 38,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 68,  "duration": 0.1},
            {"pitch": 42, "time": 2.65, "velocity": 40,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 62,  "duration": 0.1},
            {"pitch": 46, "time": 1.65, "velocity": 60,  "duration": 0.4},
            {"pitch": 46, "time": 3.65, "velocity": 58,  "duration": 0.4},
        ],
        "fill": [
            {"pitch": 36, "time": 0.0,  "velocity": 95,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 88,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 42, "time": 0.0,  "velocity": 68,  "duration": 0.1},
            {"pitch": 42, "time": 0.65, "velocity": 40,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 62,  "duration": 0.1},
            {"pitch": 42, "time": 1.65, "velocity": 38,  "duration": 0.1},
            {"pitch": 42, "time": 2.0,  "velocity": 68,  "duration": 0.1},
            {"pitch": 42, "time": 2.65, "velocity": 40,  "duration": 0.1},
            {"pitch": 42, "time": 3.0,  "velocity": 62,  "duration": 0.1},
            {"pitch": 46, "time": 1.65, "velocity": 60,  "duration": 0.4},
            {"pitch": 38, "time": 3.25, "velocity": 68,  "duration": 0.1},
            {"pitch": 38, "time": 3.5,  "velocity": 78,  "duration": 0.1},
            {"pitch": 38, "time": 3.75, "velocity": 90,  "duration": 0.1},
        ],
    },
}

_ALIASES = {
    "reggaeton": "dembow",
    "latin trap": "dembow",
    "perreo": "dembow",
    "trap minimal": "trap_minimal",
    "minimal trap": "trap_minimal",
    "trap sparse": "trap_minimal",
    "trap dense": "trap_busy",
    "trap heavy": "trap_busy",
    "boom bap": "boom_bap",
    "boom-bap": "boom_bap",
    "boom bap heavy": "boom_bap_heavy",
    "boom bap chill": "boom_bap_chill",
    "boom bap light": "boom_bap_chill",
    "rock driving": "rock_driving",
    "driving rock": "rock_driving",
    "rock halftime": "rock_halftime",
    "house deep": "house_deep",
    "deep house": "house_deep",
    "funk heavy": "funk_heavy",
    "heavy funk": "funk_heavy",
    "lofi lazy": "lofi_lazy",
    "lazy lofi": "lofi_lazy",
    "hip hop": "boom_bap",
    "hip-hop": "boom_bap",
    "jazz": "jazz_swing",
    "swing": "jazz_swing",
    "jazz swing": "jazz_swing",
    "lofi hip hop": "lofi",
    "lo-fi": "lofi",
    "lo fi": "lofi",
    "lo-fi hip-hop": "lofi",
    "uk drill": "uk_drill",
    "drill": "uk_drill",
    "bossa": "bossa_nova",
    "bossa nova": "bossa_nova",
    "neo soul": "halftime",
    "neo-soul": "halftime",
    "half time": "halftime",
    "half-time": "halftime",
    "one drop": "reggae",
    "one-drop": "reggae",
    "afrobeat": "afrobeats",
    "afro beats": "afrobeats",
}


def _normalize(genre: str) -> str:
    g = genre.lower().strip()
    if g in _PATTERNS:
        return g
    if g in _ALIASES:
        return _ALIASES[g]
    for key in _PATTERNS:
        if key in g:
            return key
    return "default"


def _humanize(velocity: int, spread: int = 8) -> int:
    """Apply random velocity variation so the same skeleton sounds different each generation."""
    return max(1, min(127, velocity + random.randint(-spread, spread)))


# Per-instrument timing tendencies: (bias_beats, spread_beats)
# Positive bias = behind the beat (laid back), negative = ahead of the beat
_TIMING: Dict[int, tuple] = {
    36: (0.000, 0.012),   # kick: centered, small jitter
    35: (0.000, 0.012),
    38: (0.006, 0.010),   # snare: laid back
    40: (0.006, 0.010),
    39: (0.000, 0.010),   # clap: neutral
    37: (0.004, 0.008),   # rimshot: slightly behind
    42: (-0.004, 0.007),  # CHH: slightly ahead (rushes)
    44: (0.000, 0.007),   # pedal HH: steady
    46: (0.000, 0.010),   # OHH: variable
    49: (0.000, 0.003),   # crash: barely moves
    51: (-0.003, 0.007),  # ride: slightly ahead
}


def _microtiming(pitch: int, base_time: float) -> float:
    """Nudge a note slightly off the grid based on instrument type."""
    bias, spread = _TIMING.get(pitch, (0.002, 0.012))  # toms default: slightly behind
    offset = bias + random.uniform(-spread, spread)
    return max(0.0, round(base_time + offset, 4))


# Hi-hat / cymbal pitches that are NEVER in the groove skeleton — they come from LAYER_LIBRARY only
_HAT_PITCHES: Set[int] = {42, 44, 46, 51}

# Named percussion layers Claude can request via drum_layers: [...]
LAYER_LIBRARY: Dict[str, List[Dict]] = {
    # Steady 8th-note closed hi-hats — rock, pop, house baseline
    "hihat_8th": [
        {"pitch": 42, "time": t * 0.5, "velocity": 80 if t % 2 == 0 else 65, "duration": 0.1}
        for t in range(8)
    ],
    # Driving 16th-note closed hi-hats — energetic, dance
    "hihat_16th": [
        {"pitch": 42, "time": t * 0.25,
         "velocity": 80 if t % 4 == 0 else (70 if t % 2 == 0 else 58), "duration": 0.1}
        for t in range(16)
    ],
    # Minimal quarter-note hi-hats — chill, sparse
    "hihat_quarter": [
        {"pitch": 42, "time": float(t), "velocity": 80 if t % 2 == 0 else 68, "duration": 0.1}
        for t in range(4)
    ],
    # Swung 8th hi-hats — boom bap, hip hop, jazz-adjacent
    "hihat_swing": [
        {"pitch": 42, "time": 0.0,  "velocity": 85, "duration": 0.1},
        {"pitch": 42, "time": 0.55, "velocity": 60, "duration": 0.1},
        {"pitch": 42, "time": 1.0,  "velocity": 82, "duration": 0.1},
        {"pitch": 42, "time": 1.55, "velocity": 57, "duration": 0.1},
        {"pitch": 42, "time": 2.0,  "velocity": 84, "duration": 0.1},
        {"pitch": 42, "time": 2.55, "velocity": 60, "duration": 0.1},
        {"pitch": 42, "time": 3.0,  "velocity": 80, "duration": 0.1},
        {"pitch": 42, "time": 3.55, "velocity": 57, "duration": 0.1},
    ],
    # Sparse trap hi-hats with open hat accents
    "hihat_trap": [
        {"pitch": 42, "time": 0.0,  "velocity": 82, "duration": 0.1},
        {"pitch": 42, "time": 0.25, "velocity": 55, "duration": 0.1},
        {"pitch": 42, "time": 0.5,  "velocity": 70, "duration": 0.1},
        {"pitch": 46, "time": 1.0,  "velocity": 58, "duration": 0.15},
        {"pitch": 42, "time": 1.5,  "velocity": 72, "duration": 0.1},
        {"pitch": 42, "time": 1.75, "velocity": 52, "duration": 0.1},
        {"pitch": 42, "time": 2.0,  "velocity": 82, "duration": 0.1},
        {"pitch": 42, "time": 2.5,  "velocity": 65, "duration": 0.1},
        {"pitch": 46, "time": 3.0,  "velocity": 55, "duration": 0.15},
        {"pitch": 42, "time": 3.5,  "velocity": 70, "duration": 0.1},
        {"pitch": 42, "time": 3.75, "velocity": 50, "duration": 0.1},
    ],
    # Open hi-hat on every offbeat — reggae, ska, dub
    "hihat_open_offbeat": [
        {"pitch": 46, "time": 0.5,  "velocity": 62, "duration": 0.2},
        {"pitch": 46, "time": 1.5,  "velocity": 58, "duration": 0.2},
        {"pitch": 46, "time": 2.5,  "velocity": 62, "duration": 0.2},
        {"pitch": 46, "time": 3.5,  "velocity": 58, "duration": 0.2},
    ],
    # Jazz ride "ding-dinga-ding" + pedal hi-hat on beats 2 and 4
    "hihat_jazz_ride": [
        {"pitch": 51, "time": 0.0,   "velocity": 82, "duration": 0.1},
        {"pitch": 51, "time": 0.667, "velocity": 62, "duration": 0.1},
        {"pitch": 51, "time": 1.0,   "velocity": 78, "duration": 0.1},
        {"pitch": 44, "time": 1.0,   "velocity": 65, "duration": 0.1},
        {"pitch": 51, "time": 2.0,   "velocity": 82, "duration": 0.1},
        {"pitch": 51, "time": 2.667, "velocity": 62, "duration": 0.1},
        {"pitch": 51, "time": 3.0,   "velocity": 78, "duration": 0.1},
        {"pitch": 44, "time": 3.0,   "velocity": 65, "duration": 0.1},
    ],
    # Open hi-hat every quarter note — house, disco, euphoric
    "hihat_open_4th": [
        {"pitch": 46, "time": 0.0, "velocity": 62, "duration": 0.2},
        {"pitch": 46, "time": 1.0, "velocity": 58, "duration": 0.2},
        {"pitch": 46, "time": 2.0, "velocity": 62, "duration": 0.2},
        {"pitch": 46, "time": 3.0, "velocity": 58, "duration": 0.2},
    ],
    # Pedal hi-hat on beats 2 and 4 only — jazz, latin, subtle pulse
    "hihat_pedal_2_4": [
        {"pitch": 44, "time": 1.0, "velocity": 72, "duration": 0.1},
        {"pitch": 44, "time": 3.0, "velocity": 70, "duration": 0.1},
    ],
}


def _build_skeleton(pattern: dict, bars: int, layers: List[str] = None) -> List[Dict]:
    groove = pattern["skeleton"]
    # "fills" (list of alternatives) takes priority over "fill" (single)
    fill_options = pattern.get("fills") or ([pattern["fill"]] if pattern.get("fill") else None)
    chosen_fill = random.choice(fill_options) if fill_options else None
    crash_on_phrase = pattern.get("crash_on_phrase_start", False)
    crash_vel = pattern.get("crash_velocity", 95)
    bar_length = pattern.get("bar_length", 1)
    active_layers = [LAYER_LIBRARY[l] for l in (layers or []) if l in LAYER_LIBRARY]

    notes = []

    for bar in range(bars):
        bar_start = bar * 4.0
        is_fill_bar = chosen_fill is not None and (bar + 1) % 4 == 0
        is_phrase_start = bar % 4 == 0

        if crash_on_phrase and is_phrase_start and bar > 0:
            notes.append({
                "pitch": 49, "time": round(bar_start, 4),
                "velocity": crash_vel, "duration": 1.0,
            })

        if is_fill_bar:
            for n in chosen_fill:
                pitch = n["pitch"]
                if pitch in _HAT_PITCHES:
                    continue  # fills are snare/tom moments — no hi-hats
                vel = _humanize(n["velocity"], spread=7) if pitch != 49 else n["velocity"]
                t = _microtiming(pitch, bar_start + n["time"])
                notes.append({"pitch": pitch, "time": t, "velocity": vel,
                               "duration": n.get("duration", 0.1)})
        else:
            bar_in_cycle = bar % bar_length
            cycle_offset = bar_in_cycle * 4.0
            for n in groove:
                if n["pitch"] in _HAT_PITCHES:
                    continue  # hi-hats/cymbals come from layers only
                t_raw = n["time"]
                if cycle_offset <= t_raw < cycle_offset + 4.0:
                    pitch = n["pitch"]
                    vel = _humanize(n["velocity"], spread=8) if pitch != 49 else n["velocity"]
                    t = _microtiming(pitch, bar_start + (t_raw - cycle_offset))
                    notes.append({"pitch": pitch, "time": t, "velocity": vel,
                                  "duration": n.get("duration", 0.1)})

        # Layer notes repeat every bar
        for layer_notes in active_layers:
            for n in layer_notes:
                pitch = n["pitch"]
                vel = _humanize(n["velocity"], spread=6)
                t = _microtiming(pitch, bar_start + n["time"])
                notes.append({"pitch": pitch, "time": t, "velocity": vel,
                              "duration": n.get("duration", 0.1)})

    return notes


def get_skeleton(genre: str, bars: int, layers: List[str] = None) -> List[Dict]:
    """Return full skeleton note list for `bars` bars of the given genre."""
    key = _normalize(genre)
    pattern = _PATTERNS.get(key, _PATTERNS["default"])
    return _build_skeleton(pattern, bars, layers)


def apply_skeleton(claude_notes: List[Dict], genre: str, bars: int,
                   layers: List[str] = None) -> List[Dict]:
    """
    Enforce the genre skeleton on Claude's drum notes.
    - Strips ALL notes on controlled pitches from Claude except ghost notes (vel < 55).
    - Python skeleton provides kick, snare, fills. Hi-hats come from layers.
    """
    key = _normalize(genre)
    pattern = _PATTERNS.get(key, _PATTERNS["default"])
    controlled: Set[int] = pattern["controlled_pitches"]
    skeleton = _build_skeleton(pattern, bars, layers)

    filtered = []
    for note in claude_notes:
        pitch = int(note.get("pitch", 0))
        vel = int(note.get("velocity", 100))
        if pitch not in controlled:
            filtered.append(note)
        elif vel < 35:
            filtered.append(note)  # ghost notes pass through

    return filtered + skeleton
