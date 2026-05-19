"""
Hardcoded drum pattern skeletons — kick, snare, hi-hats, crash, and fills.
Sources: MusicRadar, Attack Magazine, drum-patterns.com, Jazz Night School, BandLab.

Python controls: kick, snare/clap, hi-hats (CHH/OHH/pedal), crash on phrase starts,
                 and bar-4 fills (tom runs, snare rolls, hat bursts per genre).
Claude controls: ghost notes (vel < 55), toms outside fill bars, non-standard percussion.

Public API:
    get_skeleton(genre, bars)          -> List[Dict]
    apply_skeleton(notes, genre, bars) -> List[Dict]
"""
import math
from typing import List, Dict, Optional, Set

_PATTERNS: Dict[str, dict] = {

    # Sources: MusicRadar + UJAM dembow tutorials
    # Four-on-floor kick. Syncopated clap on steps 4,7,12,15.
    # Straight 8th-note hats — no swing, mechanical grid.
    "dembow": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 42, 44, 46, 49},
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
        "controlled_pitches": {35, 36, 38, 39, 40, 42, 44, 46, 49},
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
        "fill": [
            # Fill bar: normal kick+snare + intensified 32nd roll at end
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
    },

    # Sources: Attack Magazine 90s Boom Bap + Native Instruments hip-hop patterns
    # Kick on 1+2.5+3 with ghost. Swung 8th hats (+0.05 on offbeats). OHH on "and of 4".
    "boom_bap": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 42, 44, 46, 49},
        "crash_on_phrase_start": True,
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
        "fill": [
            # Snare roll on beat 4 (steps 13-16)
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
    },

    # Sources: Attack Magazine Chicago House + BandLab house tutorial
    # Four-on-floor + clap on 2+4. CHH on beats, OHH on every offbeat (jacking pattern).
    "house": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 42, 44, 46, 49},
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
        "controlled_pitches": {35, 36, 38, 39, 40, 42, 44, 46, 49},
        "crash_on_phrase_start": True,
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
        "fill": [
            # Keep kick+snare, 16th hats beats 1-3, tom descent on beat 4
            {"pitch": 36, "time": 0.0,  "velocity": 110, "duration": 0.5},
            {"pitch": 36, "time": 0.5,  "velocity": 82,  "duration": 0.5},
            {"pitch": 36, "time": 1.25, "velocity": 70,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 100, "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 108, "duration": 0.1},
            # 16th hats beats 1-3
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
            # Tom descent on beat 4 (hats stop here)
            {"pitch": 50, "time": 3.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 38, "time": 3.25, "velocity": 88,  "duration": 0.1},
            {"pitch": 48, "time": 3.5,  "velocity": 92,  "duration": 0.1},
            {"pitch": 45, "time": 3.75, "velocity": 88,  "duration": 0.1},
        ],
    },

    # Sources: Jazz Night School + drumhelper.com + Paul Wertico ride pattern
    # Feathered kick on 1+3. Pedal HH on 2+4. Ride spang-a-lang (triplet swing).
    # No closed hat — ride carries time.
    "jazz_swing": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 44, 49, 51},
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
        "controlled_pitches": {35, 36, 37, 38, 39, 40, 42, 44, 46, 49},
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
        "controlled_pitches": {35, 36, 38, 39, 40, 42, 44, 46, 49},
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
        "fill": [
            # Descending tom run — crash fires on next bar via crash_on_phrase_start
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
    },

    # Sources: joethedrummer.com Afrobeat + samplefocus Afrobeats blog
    # Dense 16th hats. Cross-stick on "and of 1" and "and of 3" (talking drum feel).
    # OHH at same positions for lift.
    "afrobeats": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 37, 38, 39, 40, 42, 44, 46, 49},
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
        "controlled_pitches": {35, 36, 38, 39, 40, 42, 44, 46, 49},
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
        "controlled_pitches": {35, 36, 38, 39, 40, 42, 44, 46, 49},
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
        "controlled_pitches": {35, 36, 37, 38, 39, 40, 42, 44, 46, 49},
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
        "controlled_pitches": {35, 36, 38, 39, 40, 42, 44, 46, 49},
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
        "fill": [
            {"pitch": 36, "time": 0.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 38, "time": 2.0,  "velocity": 118, "duration": 0.1},
            # Triplet hats beats 1-2
            {"pitch": 42, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 42, "time": 0.33, "velocity": 52,  "duration": 0.1},
            {"pitch": 42, "time": 0.67, "velocity": 70,  "duration": 0.1},
            {"pitch": 42, "time": 1.0,  "velocity": 85,  "duration": 0.1},
            {"pitch": 42, "time": 1.33, "velocity": 50,  "duration": 0.1},
            {"pitch": 42, "time": 1.67, "velocity": 68,  "duration": 0.1},
            {"pitch": 46, "time": 2.0,  "velocity": 88,  "duration": 0.5},
            # Ghost-heavy tom tumble beats 3-4
            {"pitch": 38, "time": 2.25, "velocity": 38,  "duration": 0.1},
            {"pitch": 50, "time": 2.5,  "velocity": 85,  "duration": 0.1},
            {"pitch": 38, "time": 2.75, "velocity": 35,  "duration": 0.1},
            {"pitch": 48, "time": 3.0,  "velocity": 90,  "duration": 0.1},
            {"pitch": 38, "time": 3.25, "velocity": 40,  "duration": 0.1},
            {"pitch": 45, "time": 3.5,  "velocity": 88,  "duration": 0.1},
            {"pitch": 38, "time": 3.75, "velocity": 98,  "duration": 0.1},
        ],
    },

    "default": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40, 42, 44, 46, 49},
        "crash_on_phrase_start": True,
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
}

_ALIASES = {
    "reggaeton": "dembow",
    "latin trap": "dembow",
    "perreo": "dembow",
    "boom bap": "boom_bap",
    "boom-bap": "boom_bap",
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


def _build_skeleton(pattern: dict, bars: int) -> List[Dict]:
    groove = pattern["skeleton"]
    fill = pattern.get("fill")
    crash_on_phrase = pattern.get("crash_on_phrase_start", False)
    crash_vel = pattern.get("crash_velocity", 95)
    bar_length = pattern.get("bar_length", 1)

    notes = []

    for bar in range(bars):
        bar_start = bar * 4.0
        is_fill_bar = fill is not None and (bar + 1) % 4 == 0
        is_phrase_start = bar % 4 == 0

        if crash_on_phrase and is_phrase_start:
            notes.append({
                "pitch": 49, "time": round(bar_start, 4),
                "velocity": crash_vel, "duration": 1.0,
            })

        if is_fill_bar:
            for n in fill:
                notes.append({
                    "pitch": n["pitch"],
                    "time": round(bar_start + n["time"], 4),
                    "velocity": n["velocity"],
                    "duration": n.get("duration", 0.1),
                })
        else:
            bar_in_cycle = bar % bar_length
            cycle_offset = bar_in_cycle * 4.0
            for n in groove:
                t = n["time"]
                if cycle_offset <= t < cycle_offset + 4.0:
                    notes.append({
                        "pitch": n["pitch"],
                        "time": round(bar_start + (t - cycle_offset), 4),
                        "velocity": n["velocity"],
                        "duration": n.get("duration", 0.1),
                    })

    return notes


def get_skeleton(genre: str, bars: int) -> List[Dict]:
    """Return full skeleton note list for `bars` bars of the given genre."""
    key = _normalize(genre)
    pattern = _PATTERNS.get(key, _PATTERNS["default"])
    return _build_skeleton(pattern, bars)


def apply_skeleton(claude_notes: List[Dict], genre: str, bars: int) -> List[Dict]:
    """
    Enforce the genre skeleton on Claude's drum notes.
    - Strips ALL notes on controlled pitches from Claude except ghost notes (vel < 55).
    - Claude retains toms, any non-controlled percussion, and ghost notes.
    - Python skeleton provides kick, snare, hi-hats, crash, and fills.
    """
    key = _normalize(genre)
    pattern = _PATTERNS.get(key, _PATTERNS["default"])
    controlled: Set[int] = pattern["controlled_pitches"]
    skeleton = _build_skeleton(pattern, bars)

    filtered = []
    for note in claude_notes:
        pitch = int(note.get("pitch", 0))
        vel = int(note.get("velocity", 100))
        if pitch not in controlled:
            filtered.append(note)
        elif vel < 55:
            filtered.append(note)  # ghost notes pass through

    return filtered + skeleton
