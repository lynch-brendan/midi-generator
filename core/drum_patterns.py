"""
Hardcoded drum pattern skeletons from verified sources.

The skeleton defines kick/snare/clap positions for each genre.
Claude handles hi-hats, ghost notes, open hats, toms, and fills.
apply_skeleton() merges Claude's notes with the genre skeleton.

Step → beat: step N = (N-1) * 0.25 beats (16-step grid, 4/4)
"""
import math
from typing import List, Dict, Optional, Set

# Each skeleton note: pitch, time (beats within the pattern), velocity
# bar_length: how many bars before the pattern repeats
# controlled_pitches: pitches the skeleton owns (filtered from Claude's output near skeleton positions)

_PATTERNS: Dict[str, dict] = {

    # Source: MusicRadar + UJAM dembow tutorials
    # Four-on-floor kick. Syncopated clap on steps 4,7,12,15 = the dembow bounce.
    "dembow": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 110, "duration": 0.5},
            {"pitch": 36, "time": 1.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 36, "time": 3.0,  "velocity": 103, "duration": 0.5},
            {"pitch": 39, "time": 0.75, "velocity": 88,  "duration": 0.1},
            {"pitch": 39, "time": 1.5,  "velocity": 100, "duration": 0.1},
            {"pitch": 39, "time": 2.75, "velocity": 82,  "duration": 0.1},
            {"pitch": 39, "time": 3.5,  "velocity": 100, "duration": 0.1},
        ],
    },

    # Source: eMastered + Studio Brootle trap drum pattern guides
    # Half-time snare on beat 3 only. Sparse syncopated kick. 2-bar pattern.
    "trap": {
        "bar_length": 2,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            # Bar 1
            {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 0.75, "velocity": 85,  "duration": 0.5},
            {"pitch": 38, "time": 2.0,  "velocity": 118, "duration": 0.1},
            # Bar 2
            {"pitch": 36, "time": 4.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 5.75, "velocity": 78,  "duration": 0.5},
            {"pitch": 38, "time": 6.0,  "velocity": 118, "duration": 0.1},
        ],
    },

    # Source: Attack Magazine + Native Instruments boom bap breakdown
    # Kick on steps 1,7,11 + ghost kick at step 6. Snare on 2 and 4. MPC swing feel.
    "boom_bap": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 36, "time": 1.25, "velocity": 52,  "duration": 0.5},  # ghost kick step 6
            {"pitch": 36, "time": 1.5,  "velocity": 95,  "duration": 0.5},
            {"pitch": 36, "time": 2.5,  "velocity": 88,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 100, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 100, "duration": 0.1},
        ],
    },

    # Source: Attack Magazine rolling deep house breakdown
    # Four-on-floor kick. Clap on 2 and 4. Off-beat hi-hats added by Claude.
    "house": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 115, "duration": 0.5},
            {"pitch": 36, "time": 1.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 115, "duration": 0.5},
            {"pitch": 36, "time": 3.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 39, "time": 1.0,  "velocity": 102, "duration": 0.1},
            {"pitch": 39, "time": 3.0,  "velocity": 102, "duration": 0.1},
        ],
    },

    # Source: MusicRadar Funky Drummer MIDI breakdown (Clyde Stubblefield)
    # Syncopated kick. Snare backbeats with heavy ghost note density. Claude adds ghost snares.
    "funk": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 110, "duration": 0.5},
            {"pitch": 36, "time": 0.5,  "velocity": 82,  "duration": 0.5},
            {"pitch": 36, "time": 1.25, "velocity": 70,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 100, "duration": 0.5},
            {"pitch": 36, "time": 3.0,  "velocity": 88,  "duration": 0.5},
            {"pitch": 36, "time": 3.75, "velocity": 85,  "duration": 0.5},
            # Snare backbeats on beats 2 and 4
            {"pitch": 38, "time": 1.0,  "velocity": 108, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 108, "duration": 0.1},
        ],
    },

    # Source: MusicRadar jazz MIDI guide + Jazz Night School spang-a-lang lesson
    # Feathered kick on 1+3. Pedal HH on 2+4. Ride spang-a-lang with triplet swing feel.
    "jazz_swing": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 44, 51},
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 32,  "duration": 0.5},   # feathered kick
            {"pitch": 36, "time": 2.0,  "velocity": 28,  "duration": 0.5},
            {"pitch": 44, "time": 1.0,  "velocity": 80,  "duration": 0.1},   # pedal HH
            {"pitch": 44, "time": 3.0,  "velocity": 80,  "duration": 0.1},
            # Ride: spang-a-lang (quarter + swung 8th = triplet feel)
            {"pitch": 51, "time": 0.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 0.67, "velocity": 62,  "duration": 0.1},
            {"pitch": 51, "time": 1.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 1.67, "velocity": 62,  "duration": 0.1},
            {"pitch": 51, "time": 2.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 2.67, "velocity": 62,  "duration": 0.1},
            {"pitch": 51, "time": 3.0,  "velocity": 88,  "duration": 0.1},
            {"pitch": 51, "time": 3.67, "velocity": 62,  "duration": 0.1},
        ],
    },

    # Source: Wikipedia one-drop + MusicRadar reggae MIDI programming guide
    # ONE-DROP: kick AND cross-stick land ONLY on beat 3. No kick on beat 1.
    "reggae": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            {"pitch": 36, "time": 2.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 37, "time": 2.0,  "velocity": 100, "duration": 0.1},
        ],
    },

    # Source: scriptandpad.com + Native Instruments drum patterns guide
    # Classic backbeat. Kick on 1+3, snare on 2+4, hi-hats added by Claude.
    "rock": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 115, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 115, "duration": 0.1},
        ],
    },

    # Safe/unverified fallback for Nigerian Afrobeats (no authoritative step grid found).
    # Kick on 1+3, snare on 2+4. Claude adds shaker, talking drum character via ghost notes.
    "afrobeats": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 108, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 105, "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 100, "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 100, "duration": 0.1},
        ],
    },

    # Source: Attack Magazine + BandLab UK Drill beat guides
    # 2-bar. Grime-derived hi-hat (2-2-1) added by Claude. Snare on beat 3 only (half-time).
    "uk_drill": {
        "bar_length": 2,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            # Bar 1
            {"pitch": 36, "time": 0.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 3.5,  "velocity": 90,  "duration": 0.5},
            {"pitch": 38, "time": 2.0,  "velocity": 118, "duration": 0.1},
            # Bar 2
            {"pitch": 36, "time": 4.0,  "velocity": 112, "duration": 0.5},
            {"pitch": 36, "time": 5.0,  "velocity": 88,  "duration": 0.5},
            {"pitch": 38, "time": 6.0,  "velocity": 118, "duration": 0.1},
            {"pitch": 38, "time": 6.75, "velocity": 90,  "duration": 0.1},
        ],
    },

    # Based on boom bap structure — the genre difference is sample choice and humanization.
    # Kick on steps 1,7,9. Snare on 2+4. Claude adds open hat on "and of 2".
    "lofi": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            {"pitch": 36, "time": 0.0,  "velocity": 100, "duration": 0.5},
            {"pitch": 36, "time": 1.5,  "velocity": 88,  "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 95,  "duration": 0.5},
            {"pitch": 38, "time": 1.0,  "velocity": 95,  "duration": 0.1},
            {"pitch": 38, "time": 3.0,  "velocity": 90,  "duration": 0.1},
        ],
    },

    # Source: drum-patterns.com/bossa-nova-1 (exact step grid confirmed)
    # 3-2 son clave on rimshot. Kick on steps 1,7,9,15. 2-bar pattern.
    "bossa_nova": {
        "bar_length": 2,
        "controlled_pitches": {35, 36, 37, 38, 39, 40},
        "skeleton": [
            # Kick both bars: steps 1,7,9,15
            {"pitch": 36, "time": 0.0,  "velocity": 85, "duration": 0.5},
            {"pitch": 36, "time": 1.5,  "velocity": 78, "duration": 0.5},
            {"pitch": 36, "time": 2.0,  "velocity": 82, "duration": 0.5},
            {"pitch": 36, "time": 3.5,  "velocity": 75, "duration": 0.5},
            {"pitch": 36, "time": 4.0,  "velocity": 85, "duration": 0.5},
            {"pitch": 36, "time": 5.5,  "velocity": 78, "duration": 0.5},
            {"pitch": 36, "time": 6.0,  "velocity": 82, "duration": 0.5},
            {"pitch": 36, "time": 7.5,  "velocity": 75, "duration": 0.5},
            # Bar 1 rimshot (3-side of 3-2 clave): steps 1,7,13
            {"pitch": 37, "time": 0.0,  "velocity": 90, "duration": 0.1},
            {"pitch": 37, "time": 1.5,  "velocity": 85, "duration": 0.1},
            {"pitch": 37, "time": 3.0,  "velocity": 90, "duration": 0.1},
            # Bar 2 rimshot (2-side of 3-2 clave): steps 5,11 of bar 2
            {"pitch": 37, "time": 5.0,  "velocity": 90, "duration": 0.1},
            {"pitch": 37, "time": 6.5,  "velocity": 85, "duration": 0.1},
        ],
    },

    # Half-time / neo-soul: snare on beat 3 only. Kick on beat 1 only.
    "halftime": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            {"pitch": 36, "time": 0.0, "velocity": 108, "duration": 0.5},
            {"pitch": 38, "time": 2.0, "velocity": 118, "duration": 0.1},
        ],
    },

    # Default fallback: straight kick on 1+3, snare on 2+4
    "default": {
        "bar_length": 1,
        "controlled_pitches": {35, 36, 38, 39, 40},
        "skeleton": [
            {"pitch": 36, "time": 0.0, "velocity": 105, "duration": 0.5},
            {"pitch": 36, "time": 2.0, "velocity": 100, "duration": 0.5},
            {"pitch": 38, "time": 1.0, "velocity": 105, "duration": 0.1},
            {"pitch": 38, "time": 3.0, "velocity": 105, "duration": 0.1},
        ],
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


def get_skeleton(genre: str, bars: int) -> List[Dict]:
    """Return full skeleton note list for `bars` bars of the given genre."""
    key = _normalize(genre)
    pattern = _PATTERNS.get(key, _PATTERNS["default"])
    bar_length = pattern["bar_length"]
    base = pattern["skeleton"]
    cycle_beats = bar_length * 4.0
    repeats = math.ceil(bars / bar_length)

    notes = []
    for rep in range(repeats):
        offset = rep * cycle_beats
        for n in base:
            t = n["time"] + offset
            if t < bars * 4.0:
                notes.append({
                    "pitch": n["pitch"],
                    "time": round(t, 4),
                    "velocity": n["velocity"],
                    "duration": n.get("duration", 0.1),
                })
    return notes


def apply_skeleton(claude_notes: List[Dict], genre: str, bars: int) -> List[Dict]:
    """
    Enforce the genre skeleton on Claude's drum notes.
    - Keeps Claude's hi-hats, toms, cymbals, open hats.
    - Keeps Claude's ghost notes (velocity < 55) even on controlled pitches.
    - Replaces skeleton-pitch positions with hardcoded skeleton notes.
    """
    key = _normalize(genre)
    pattern = _PATTERNS.get(key, _PATTERNS["default"])
    controlled: Set[int] = pattern["controlled_pitches"]
    skeleton = get_skeleton(genre, bars)

    # Build a lookup: (pitch, time) for skeleton positions (rounded to 0.05 tolerance bins)
    TOLERANCE = 0.14

    def _conflicts(pitch: int, time: float) -> bool:
        return any(
            n["pitch"] == pitch and abs(n["time"] - time) < TOLERANCE
            for n in skeleton
        )

    filtered = []
    for note in claude_notes:
        pitch = int(note.get("pitch", 0))
        time = float(note.get("time", 0))
        vel = int(note.get("velocity", 100))

        if pitch not in controlled:
            filtered.append(note)
        elif vel < 55:
            filtered.append(note)  # keep ghost notes even at skeleton pitches
        elif not _conflicts(pitch, time):
            filtered.append(note)  # off-position hit — keep it

    return filtered + skeleton
