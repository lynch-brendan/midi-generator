"""
Sample-based guitar renderer.

Detects chords from simultaneous MIDI notes and plays real strummed recordings.
Single notes fall through to FluidSynth (caller handles the fallback).

Sample directories:
  samples/guitar_acoustic/       — NoiseCollector Yamaha acoustic (CC-BY)
  samples/guitar_clean_electric/ — godlesswonder Fender Strat (CC0)
  samples/guitar_distorted/      — SpeedY palm-muted distorted (CC0)

GM patch routing:
  24 nylon, 25 steel, 31 harmonics → acoustic
  26 jazz, 27 clean               → clean electric
  28 muted, 29 overdrive, 30 dist → distorted
"""
import wave, struct, array, re, math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SAMPLE_RATE = 44100
SAMPLES_BASE = Path(__file__).parent.parent / "samples"

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_PC: Dict[str, int] = {n: i for i, n in enumerate(NOTE_NAMES)}
_PC.update({"Db": 1, "Eb": 3, "Fb": 4, "Gb": 6, "Ab": 8, "Bb": 10, "Cb": 11})

# Ordered by how "complete" a match should be (more specific first)
CHORD_TEMPLATES: List[Tuple[str, List[int]]] = [
    ("maj7", [0, 4, 7, 11]),
    ("m7",   [0, 3, 7, 10]),
    ("7",    [0, 4, 7, 10]),
    ("dim",  [0, 3, 6]),
    ("aug",  [0, 4, 8]),
    ("6",    [0, 4, 7, 9]),
    ("m6",   [0, 3, 7, 9]),
    ("min",  [0, 3, 7]),
    ("maj",  [0, 4, 7]),
    ("5",    [0, 7]),
]

PATCH_TO_STYLE = {
    24: "acoustic", 25: "acoustic", 31: "acoustic",
    26: "clean_electric", 27: "clean_electric",
    28: "distorted", 29: "distorted", 30: "distorted",
}
STYLE_TO_DIR = {
    "acoustic": "guitar_acoustic",
    "clean_electric": "guitar_clean_electric",
    "distorted": "guitar_distorted",
}

# Notes within this many beats of each other = one strum event
STRUM_WINDOW = 0.1

_sample_cache: Dict[str, List[float]] = {}
_chord_index_cache: Dict[str, Dict[Tuple[int, str], Path]] = {}


# ---------------------------------------------------------------------------
# Index builders — parse filenames into (pitch_class, quality) keys
# ---------------------------------------------------------------------------

def _parse_clean_electric(path: Path) -> Optional[Tuple[int, str]]:
    """Parse A_Maj.wav / A#_min.wav"""
    m = re.match(r'^([A-G]#?)_(Maj|min)\.wav$', path.name, re.IGNORECASE)
    if not m:
        return None
    pc = _PC.get(m.group(1))
    if pc is None:
        return None
    return (pc, "maj" if m.group(2).lower() == "maj" else "min")


def _parse_acoustic_name(stem: str) -> Optional[Tuple[int, str]]:
    """Parse acoustic filename stems into (pc, quality)."""
    # Strip known prefixes
    for pre in ["yamaha_", "yamah_", "chord_", "Yamaha_"]:
        if stem.lower().startswith(pre.lower()):
            stem = stem[len(pre):]
            break

    # Skip non-musical files
    skip_words = ["fingerpluck", "fretnoise", "fret_noise", "body_noise",
                  "off_timing", "abstract", "ouch", "ugly", "torture",
                  "inv", "noise", "twang", "vibrato", "riff", "blues",
                  "pattern", "pluck", "timing"]
    if any(w in stem.lower() for w in skip_words):
        return None

    # Normalise "flat" → b and "sharp" → # in the stem
    stem = stem.replace("flat", "b").replace("sharp", "#")
    # Handle A+ → Aaug
    stem = stem.replace("+", "aug")

    # Parse root note (1-2 chars)
    if len(stem) < 1 or stem[0] not in "ABCDEFG":
        return None

    if len(stem) >= 2 and stem[1] in ("#", "b"):
        root_str = stem[:2]
        rest = stem[2:]
    else:
        root_str = stem[0]
        rest = stem[1:]

    pc = _PC.get(root_str)
    if pc is None:
        return None

    rest = rest.strip("_- ")

    # Quality mapping — check longest match first
    quality_map = [
        ("maj7", "maj7"), ("m7", "m7"), ("m6", "m6"),
        ("min7", "m7"), ("min6", "m6"),
        ("dim", "dim"), ("aug", "aug"),
        ("min", "min"), ("m", "min"),
        ("7", "7"), ("6", "6"), ("9", "7"),
        ("rock", "maj"), ("5th", "5"), ("5", "5"), ("oct", "5"),
    ]
    quality = "maj"
    for suffix, q in quality_map:
        if rest.lower().startswith(suffix):
            quality = q
            break

    return (pc, quality)


def _parse_acoustic(path: Path) -> Optional[Tuple[int, str]]:
    if not path.name.endswith(".wav"):
        return None
    return _parse_acoustic_name(path.stem)


def _parse_distorted(path: Path) -> Optional[Tuple[int, str]]:
    """Parse Dist_Chr_X_pm.wav filenames."""
    name = path.stem
    if not name.startswith("Dist_Chr_"):
        return None
    # Strip Dist_Chr_ prefix and trailing _pm / _up_pm
    inner = name[len("Dist_Chr_"):]
    inner = re.sub(r"_up_pm$|_pm$", "", inner)

    # Map known chord suffixes
    chord_map = {
        "Arock": ("A", "maj"), "A5th": ("A", "5"), "A_oct": ("A", "5"),
        "A&D_5th_fret": ("A", "5"), "A&D_strs": ("A", "5"),
        "B_Mid-G": ("B", "maj"), "Bmin_rock": ("B", "min"),
        "Crock": ("C", "maj"), "Cmin": ("C", "min"),
        "D&G_5th_frt": ("D", "5"), "D5th": ("D", "5"), "D_oct": ("D", "5"),
        "Drock": ("D", "maj"),
        "EMj": ("E", "maj"), "Eminor": ("E", "min"), "E5th": ("E", "5"),
        "E_oct": ("E", "5"), "E_rock": ("E", "maj"),
        "Emin_rock": ("E", "min"), "Emj_rock": ("E", "maj"),
        "G_rock": ("G", "maj"), "Gmin": ("G", "min"),
    }
    if inner in chord_map:
        root_str, quality = chord_map[inner]
        pc = _PC.get(root_str)
        return (pc, quality) if pc is not None else None

    # Generic: single letter or letter+quality
    return _parse_acoustic_name(inner)


def _build_index(style: str) -> Dict[Tuple[int, str], Path]:
    dir_name = STYLE_TO_DIR.get(style)
    if not dir_name:
        return {}
    sample_dir = SAMPLES_BASE / dir_name
    if not sample_dir.exists():
        return {}

    index: Dict[Tuple[int, str], Path] = {}
    parsers = {
        "clean_electric": _parse_clean_electric,
        "acoustic": _parse_acoustic,
        "distorted": _parse_distorted,
    }
    parser = parsers.get(style)
    if parser is None:
        return {}

    for path in sample_dir.glob("*.wav"):
        result = parser(path)
        if result is None:
            continue
        key = result
        # Don't overwrite — prefer shorter filename (simpler variant)
        if key not in index or len(path.name) < len(index[key].name):
            index[key] = path

    return index


def _get_index(style: str) -> Dict[Tuple[int, str], Path]:
    if style not in _chord_index_cache:
        _chord_index_cache[style] = _build_index(style)
    return _chord_index_cache[style]


# ---------------------------------------------------------------------------
# Sample loading
# ---------------------------------------------------------------------------

def _load_sample(path: Path, max_seconds: float = 4.0) -> Optional[List[float]]:
    key = str(path)
    if key in _sample_cache:
        return _sample_cache[key]
    try:
        with wave.open(str(path), "r") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            # Only read up to max_seconds worth of frames
            max_frames = int(framerate * max_seconds)
            n_frames = min(wf.getnframes(), max_frames)
            raw = wf.readframes(n_frames)

        if sampwidth == 2:
            ints = array.array("h", raw)
            floats = [s / 32768.0 for s in ints]
        elif sampwidth == 3:
            floats = []
            for i in range(0, len(raw) - 2, 3):
                val = int.from_bytes(raw[i:i + 3], "little", signed=True)
                floats.append(val / 8388608.0)
        elif sampwidth == 1:
            ints = array.array("B", raw)
            floats = [(s - 128) / 128.0 for s in ints]
        else:
            return None

        # Mix stereo to mono
        if n_channels == 2:
            floats = [(floats[i] + floats[i + 1]) / 2.0
                      for i in range(0, len(floats) - 1, 2)]

        # Resample to SAMPLE_RATE if needed
        if framerate != SAMPLE_RATE:
            ratio = framerate / SAMPLE_RATE
            new_len = int(len(floats) / ratio)
            resampled = []
            for i in range(new_len):
                pos = i * ratio
                idx = int(pos)
                frac = pos - idx
                if idx + 1 < len(floats):
                    resampled.append(floats[idx] * (1 - frac) + floats[idx + 1] * frac)
                elif idx < len(floats):
                    resampled.append(floats[idx])
            floats = resampled

        _sample_cache[key] = floats
        return floats
    except Exception as e:
        print(f"  [guitar_synth] could not load {path.name}: {e}")
        return None


# ---------------------------------------------------------------------------
# Chord detection
# ---------------------------------------------------------------------------

def _detect_chord(pitches: List[int]) -> Optional[Tuple[int, str]]:
    """Return (root_pitch_class, quality) or None if no clean chord found."""
    pcs = set(p % 12 for p in pitches)
    # Lowest note is almost always the root on guitar
    bass_pc = min(pitches) % 12

    best_root = bass_pc
    best_quality = "maj"
    best_score = -99.0

    for root in range(12):
        for quality, intervals in CHORD_TEMPLATES:
            chord_pcs = set((root + i) % 12 for i in intervals)
            hits = len(pcs & chord_pcs)
            misses = len(pcs - chord_pcs)
            score = hits - misses * 0.65
            # Bonus for root matching the bass note — guitar chords are almost always root-position
            if root == bass_pc:
                score += 1.0
            if score > best_score:
                best_score = score
                best_root = root
                best_quality = quality

    # Require a meaningful match — skip if the notes don't form a recognisable chord
    if best_score < 1.5:
        return None
    return best_root, best_quality


# ---------------------------------------------------------------------------
# Sample lookup with fallback chain
# ---------------------------------------------------------------------------

_QUALITY_FALLBACKS: Dict[str, List[str]] = {
    "maj":  ["maj", "6", "7", "min"],
    "min":  ["min", "m7", "m6", "maj"],
    "7":    ["7", "maj", "6", "min"],
    "m7":   ["m7", "min", "7", "maj"],
    "maj7": ["maj7", "maj", "7", "6"],
    "6":    ["6", "maj", "7", "min"],
    "m6":   ["m6", "min", "m7", "maj"],
    "5":    ["5", "maj", "7", "min"],
    "dim":  ["dim", "min", "m7", "maj"],
    "aug":  ["aug", "maj", "7", "min"],
}


def _find_sample(index: Dict[Tuple[int, str], Path],
                 root_pc: int, quality: str) -> Optional[Path]:
    fallbacks = _QUALITY_FALLBACKS.get(quality, ["maj", "min"])

    # Try exact root first
    for q in fallbacks:
        if (root_pc, q) in index:
            return index[(root_pc, q)]

    # Widen search to nearest roots only — beyond 2 semitones a wrong chord is worse than silence
    for dist in range(1, 3):
        for adj in [(root_pc + dist) % 12, (root_pc - dist) % 12]:
            for q in fallbacks:
                if (adj, q) in index:
                    return index[(adj, q)]

    return None


# ---------------------------------------------------------------------------
# Note grouping
# ---------------------------------------------------------------------------

def _group_notes(notes: List[dict], window_beats: float) -> List[List[dict]]:
    """Group notes that start within window_beats of each other into strum events."""
    if not notes:
        return []
    sorted_notes = sorted(notes, key=lambda n: float(n["time"]))
    groups: List[List[dict]] = []
    current = [sorted_notes[0]]
    anchor = float(sorted_notes[0]["time"])

    for note in sorted_notes[1:]:
        t = float(note["time"])
        if t - anchor <= window_beats:
            current.append(note)
        else:
            groups.append(current)
            current = [note]
            anchor = t

    groups.append(current)
    return groups


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def is_available(gm_patch: int) -> bool:
    style = PATCH_TO_STYLE.get(gm_patch)
    if not style:
        return False
    return bool(_get_index(style))


def render_guitar_pattern(
    notes: List[dict],
    tempo_bpm: int,
    gm_patch: int,
    output_path: Path,
    bars: int = 4,
) -> bool:
    """
    Render guitar notes using real strummed chord samples.

    Chord groups (2+ simultaneous notes) → matched sample.
    Single notes → silence (they ring into nearby chord strums naturally).
    Returns False if samples aren't available or if the pattern is mostly
    single notes (caller should fall back to FluidSynth).
    """
    style = PATCH_TO_STYLE.get(gm_patch, "acoustic")
    index = _get_index(style)
    if not index:
        return False

    groups = _group_notes(notes, STRUM_WINDOW)
    chord_groups = [g for g in groups if len(g) >= 2]
    single_groups = [g for g in groups if len(g) == 1]

    # Fall back to FluidSynth when pattern is melody-dominant
    if not chord_groups or len(single_groups) > len(chord_groups) * 2:
        return False

    try:
        beats_per_second = tempo_bpm / 60.0
        total_samples = int((bars * 4.0 / beats_per_second) * SAMPLE_RATE)
        buf = [0.0] * total_samples

        for group in groups:
            start_beat = float(min(n["time"] for n in group))
            velocity = max(min(int(n.get("velocity", 100)), 127) for n in group)
            duration_beats = max(float(n.get("duration", 1.0)) for n in group)

            if len(group) >= 2:
                pitches = [int(n["pitch"]) for n in group]
                result = _detect_chord(pitches)
                if result is None:
                    continue  # unrecognisable cluster — skip rather than play a wrong chord
                root_pc, quality = result
            else:
                continue  # single melody note — let the surrounding chord strums carry it

            sample_path = _find_sample(index, root_pc, quality)
            if sample_path is None:
                continue

            raw = _load_sample(sample_path, max_seconds=4.0)
            if raw is None:
                continue

            # Trim to note duration + 1.5 s natural decay
            play_sec = duration_beats / beats_per_second + 1.5
            use_len = min(len(raw), int(play_sec * SAMPLE_RATE))
            tone = list(raw[:use_len])

            # Fade out last 0.4 s to avoid clicks
            fade_len = min(int(0.4 * SAMPLE_RATE), use_len)
            for i in range(use_len - fade_len, use_len):
                tone[i] *= 1.0 - (i - (use_len - fade_len)) / fade_len

            vel_scale = velocity / 127.0
            start_sample = int(start_beat / beats_per_second * SAMPLE_RATE)
            for i, s in enumerate(tone):
                dest = start_sample + i
                if dest < total_samples:
                    buf[dest] += s * vel_scale

        peak = max(abs(s) for s in buf) if buf else 0.0
        if peak > 0.9:
            scale = 0.9 / peak
            buf = [s * scale for s in buf]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            for s in buf:
                v = int(max(-32767, min(32767, s * 32767)))
                wf.writeframes(struct.pack("<hh", v, v))

        return True

    except Exception as e:
        print(f"  [guitar_synth] render failed: {e}")
        return False
