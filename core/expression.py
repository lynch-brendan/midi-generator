"""
Code-driven expression: translate a variation's expression label + GM patch
into per-note bend/vibrato data placed at musically meaningful positions.

Claude picks the label ("none"/"subtle"/"moderate"/"expressive").
We pick the exact numbers — consistent, tunable, no AI guesswork.
"""
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Instrument category detection from GM patch
# ---------------------------------------------------------------------------

def _instrument_category(gm_patch: int, is_drums: bool = False) -> str:
    if is_drums:
        return "drums"
    p = gm_patch
    if p <= 7:   return "piano"
    if p <= 15:  return "chromatic_perc"
    if p <= 23:  return "organ"
    if p <= 31:  return "guitar"
    if p <= 39:  return "bass"
    if p <= 47:  return "strings"
    if p <= 55:  return "ensemble"
    if p <= 63:  return "brass"
    if p <= 71:  return "reed"
    if p <= 79:  return "pipe"
    if p <= 87:  return "synth_lead"
    return "other"


# ---------------------------------------------------------------------------
# Per-category, per-level profiles
# Format: (vibrato_depth, vibrato_delay, slide_in, slide_out, min_dur_vibrato, min_dur_slide)
# ---------------------------------------------------------------------------

_NO_EXPR = (0.0, 0.0, 0.0, 0.0, 99.0, 99.0)

_PROFILES: Dict[str, Dict[str, tuple]] = {
    "piano":         {"subtle": _NO_EXPR, "moderate": _NO_EXPR, "expressive": _NO_EXPR},
    "chromatic_perc":{"subtle": _NO_EXPR, "moderate": _NO_EXPR, "expressive": _NO_EXPR},
    "organ":         {"subtle": _NO_EXPR, "moderate": _NO_EXPR, "expressive": _NO_EXPR},
    "bass":          {"subtle": _NO_EXPR, "moderate": _NO_EXPR, "expressive": _NO_EXPR},
    "drums":         {"subtle": _NO_EXPR, "moderate": _NO_EXPR, "expressive": _NO_EXPR},
    "guitar": {
        # (vibrato_depth, vibrato_delay, slide_in, slide_out, min_dur_vibrato, min_dur_slide)
        "subtle":     (0.15, 0.4, -0.4, 0.0,  1.5, 0.75),
        "moderate":   (0.20, 0.3, -0.7, 0.7,  1.0, 0.5),
        "expressive": (0.30, 0.25,-1.0, 1.5,  0.75, 0.5),
    },
    "strings": {
        "subtle":     (0.20, 0.4, -0.3, 0.0,  1.5, 1.0),
        "moderate":   (0.30, 0.35,-0.5, 0.0,  1.0, 0.75),
        "expressive": (0.40, 0.3, -0.8, 0.3,  0.75, 0.5),
    },
    "ensemble": {
        "subtle":     (0.15, 0.5, 0.0,  0.0,  2.0, 99.0),
        "moderate":   (0.20, 0.4, -0.3, 0.0,  1.5, 99.0),
        "expressive": (0.30, 0.35,-0.5, 0.0,  1.0, 99.0),
    },
    "brass": {
        "subtle":     (0.15, 0.45,-0.4, 0.0,  1.5, 0.75),
        "moderate":   (0.22, 0.35,-0.7, 0.0,  1.0, 0.5),
        "expressive": (0.30, 0.3, -1.0, 0.5,  0.75, 0.5),
    },
    "reed": {
        "subtle":     (0.15, 0.45,-0.3, 0.0,  1.5, 0.75),
        "moderate":   (0.22, 0.35,-0.6, 0.0,  1.0, 0.5),
        "expressive": (0.30, 0.3, -0.9, 0.3,  0.75, 0.5),
    },
    "pipe": {
        "subtle":     (0.12, 0.55,-0.2, 0.0,  2.0, 1.0),
        "moderate":   (0.18, 0.45,-0.4, 0.0,  1.5, 0.75),
        "expressive": (0.25, 0.4, -0.6, 0.0,  1.0, 0.5),
    },
    "synth_lead": {
        "subtle":     (0.10, 0.5, -0.3, 0.0,  2.0, 1.0),
        "moderate":   (0.15, 0.4, -0.5, 0.3,  1.5, 0.75),
        "expressive": (0.22, 0.35,-0.8, 0.5,  1.0, 0.5),
    },
    "other": {
        "subtle":     (0.12, 0.5, -0.3, 0.0,  1.5, 0.75),
        "moderate":   (0.20, 0.4, -0.5, 0.0,  1.0, 0.5),
        "expressive": (0.28, 0.35,-0.8, 0.3,  0.75, 0.5),
    },
}


# ---------------------------------------------------------------------------
# Phrase analysis
# ---------------------------------------------------------------------------

def _find_phrases(notes: List[Dict]) -> List[List[int]]:
    """Split note indices into phrases separated by gaps > 0.3 beats."""
    if not notes:
        return []
    sorted_idx = sorted(range(len(notes)), key=lambda i: notes[i]["time"])
    phrases: List[List[int]] = [[sorted_idx[0]]]
    for i in range(1, len(sorted_idx)):
        prev = sorted_idx[i - 1]
        curr = sorted_idx[i]
        gap = notes[curr]["time"] - (notes[prev]["time"] + notes[prev]["duration"])
        if gap > 0.3:
            phrases.append([])
        phrases[-1].append(curr)
    return phrases


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def apply_expression(
    notes: List[Dict[str, Any]],
    gm_patch: int,
    expression_level: str,
    is_drums: bool = False,
) -> List[Dict[str, Any]]:
    """
    Post-process a note list and add bend/vibrato fields based on the
    expression level and instrument category.

    Returns a new list of note dicts (originals are not mutated).
    """
    level = expression_level if expression_level in ("subtle", "moderate", "expressive") else "subtle"
    category = _instrument_category(gm_patch, is_drums)
    profile = _PROFILES.get(category, _PROFILES["other"]).get(level, _NO_EXPR)

    vib_depth, vib_delay, slide_in, slide_out, min_dur_vib, min_dur_slide = profile

    if vib_depth == 0.0 and slide_in == 0.0 and slide_out == 0.0:
        return notes  # nothing to do (piano, drums, bass)

    # Work on copies
    result = [dict(n) for n in notes]

    phrases = _find_phrases(result)

    for phrase_indices in phrases:
        if not phrase_indices:
            continue

        phrase_notes = [result[i] for i in phrase_indices]

        # Phrase entry (first note): slide in
        first_idx = phrase_indices[0]
        first_note = result[first_idx]
        if slide_in != 0.0 and first_note["duration"] >= min_dur_slide:
            first_note["bend_start"] = slide_in
            first_note["vibrato_delay"] = vib_delay

        # Phrase peak (highest pitch, long enough): vibrato
        if vib_depth > 0.0:
            long_notes = [(i, result[i]) for i in phrase_indices if result[i]["duration"] >= min_dur_vib]
            if long_notes:
                # Pick highest pitch among long notes
                peak_idx, peak_note = max(long_notes, key=lambda x: x[1]["pitch"])
                peak_note["vibrato"] = vib_depth
                peak_note["vibrato_delay"] = vib_delay

        # Phrase exit (last note, long enough): slide out
        last_idx = phrase_indices[-1]
        last_note = result[last_idx]
        if slide_out != 0.0 and last_note["duration"] >= min_dur_slide:
            last_note["bend_end"] = slide_out

    return result
