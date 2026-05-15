"""
Claude API client for music generation.
Uses prompt caching on the system prompt to reduce costs on repeated calls.
"""
import json
import re
import random
from pathlib import Path
from typing import Dict, Any, Generator

import anthropic

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000
SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.txt"


def _load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(f"System prompt not found: {SYSTEM_PROMPT_PATH}")
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _extract_json(text: str) -> str:
    """Strip any accidental markdown fences Claude may add despite instructions."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    if fence:
        return fence.group(1).strip()
    return text


def generate_variations(prompt: str) -> Dict[str, Any]:
    """
    Call Claude to generate 5 musical variations for the given prompt.
    Returns the parsed JSON response dict.
    Raises ValueError if the response cannot be parsed.
    """
    client = anthropic.Anthropic()
    system_prompt = _load_system_prompt()

    user_message = _user_message(prompt)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                # Cache the system prompt — it's identical across all calls
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {"role": "user", "content": user_message}
        ],
    )

    raw_text = ""
    for block in response.content:
        if block.type == "text":
            raw_text = block.text
            break

    if not raw_text:
        raise ValueError("Claude returned an empty response")

    clean_text = _extract_json(raw_text)

    try:
        data = json.loads(clean_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Claude response is not valid JSON: {e}\n"
            f"Raw response (first 500 chars):\n{raw_text[:500]}"
        ) from e

    if "variations" not in data or not isinstance(data["variations"], list):
        raise ValueError(f"Response missing 'variations' array. Keys found: {list(data.keys())}")

    if len(data["variations"]) == 0:
        raise ValueError("Claude returned 0 variations")

    # Log cache stats if available
    if hasattr(response, "usage") and response.usage:
        usage = response.usage
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0
        if cached > 0:
            print(f"  [cache] {cached} tokens served from prompt cache")

    return data


_CREATIVE_ANGLES = [
    "Lean into contrast — some variations should feel almost opposite to each other.",
    "Think about what a completely unexpected artist would do with this prompt.",
    "Prioritize rhythmic surprises: syncopation, odd phrasing, displaced accents.",
    "Push the tempo extremes — very slow AND very fast should both appear.",
    "Find the most obscure, interesting era or scene that fits this prompt.",
    "Make at least two variations feel emotionally opposite (tense vs. relaxed, dark vs. bright).",
    "Think about register extremes — some ideas very high, some very low.",
    "Consider a variation that strips everything down to its barest bones.",
    "Find the groove — at least one variation should make people want to move.",
    "Explore unusual key choices or modal colors that aren't the obvious pick.",
    "Think across decades: one variation could feel vintage, one futuristic.",
    "Vary the density sharply: some very sparse, some very dense.",
]


def _lock_constraints(lock_key: str = None, lock_tempo: int = None) -> str:
    parts = []
    if lock_key:
        parts.append(
            f'LOCKED KEY: Every single variation MUST use "{lock_key}" as its key and scale_notes. '
            "Override the normal key-variation rule — do NOT vary the tonal center."
        )
    if lock_tempo:
        parts.append(
            f"LOCKED TEMPO: Every single variation MUST use exactly {lock_tempo} BPM. "
            "Do NOT vary the tempo across variations."
        )
    return ("\n\n" + "\n".join(parts)) if parts else ""


def _user_message(prompt: str, lock_key: str = None, lock_tempo: int = None) -> str:
    angle = random.choice(_CREATIVE_ANGLES)
    key_rule = (
        f'Every variation MUST use "{lock_key}" as its key and scale_notes.'
        if lock_key else
        "Each variation must have its own key and scale_notes — vary the tonal center across the 5 variations."
    )
    return (
        f'Generate 5 musical variations for: "{prompt}"\n\n'
        f"Creative direction for this session: {angle}\n\n"
        f"{key_rule} "
        "Return the complete JSON object with all 5 variations, each with a full note sequence and its own instrument + gm_patch fields. "
        "Each variation must include a 'bars' field (1, 2, 4, or 8) — choose based on musical role per the BAR LENGTH GUIDE. "
        "The last note must land at or near bars × 4.0 beats. "
        f"Remember: return ONLY raw JSON, no markdown."
        + _lock_constraints(lock_key, lock_tempo)
    )


def _seed_user_message(prompt: str, seed: dict, lock_key: str = None, lock_tempo: int = None) -> str:
    musical_fields = {k: v for k, v in seed.items() if k not in ("midi_url", "wav_url", "note_count")}
    seed_json = json.dumps(musical_fields, indent=2)
    direction = prompt.strip() or "explore natural variations"
    seed_instrument = seed.get("instrument", "the existing instrument")
    key_rule = (
        f'Every variation MUST use "{lock_key}" as its key and scale_notes.'
        if lock_key else
        "Each variation must have its own key and scale_notes."
    )
    return (
        f"The user has a musical variation they want to build on.\n\n"
        f"SEED VARIATION:\n{seed_json}\n\n"
        f"USER REQUEST: \"{direction}\"\n\n"
        "Use your musician's ear to decide the right instrument(s). If the user wants the same thing evolved — same feel, "
        f"different pattern, more intensity — stay on {seed_instrument} or something close. If they're asking for a "
        "different sound or a new part, pick what fits naturally. Don't overthink it: what would a session player reach for?\n\n"
        "Generate 5 variations that fulfill the request. Each must differ from the others — vary density, register, and dynamics. "
        "The 5 variations must also differ from the seed itself. "
        f"{key_rule} "
        "Each variation must include a 'bars' field. "
        "The last note must land at or near bars × 4.0 beats. "
        "Return ONLY raw JSON, no markdown."
        + _lock_constraints(lock_key, lock_tempo)
    )


def stream_thinking(prompt: str) -> Generator[Dict, None, None]:
    """Stream a funny one-liner reaction to the user's prompt into the speech bubble."""
    client = anthropic.Anthropic()
    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=40,
        messages=[{
            "role": "user",
            "content": (
                f'A musician just got this request: "{prompt}". '
                "Write their ONE punchy reaction — 5-12 words, all lowercase, like a text message. "
                "Be specific and funny about exactly what was asked for. No quotes, no period at the end. "
                'Examples: "dark jazz piano?? this is literally my moment" / "lofi beats say less" / "upbeat summer vibes?? i was born for this" / "jazz fusion bold choice i respect it" / "sad guitar ok i\'ll need a minute"'
            ),
        }],
    ) as stream:
        for text in stream.text_stream:
            yield {"type": "thought", "token": text}


def stream_variations(prompt: str, seed_variation: dict = None, lock_key: str = None, lock_tempo: int = None) -> Generator[Dict, None, None]:
    """
    Stream Claude's response and yield parsed objects as they become available.
    Yields: one 'meta' dict first, then one 'variation' dict per variation, then 'done'.
    If seed_variation is provided, Claude interprets the prompt to decide whether to evolve
    the existing sound or generate a complementary part on a different instrument.
    lock_key and lock_tempo pin all variations to an exact key/tempo when set.
    """
    client = anthropic.Anthropic()
    system_prompt = _load_system_prompt()

    if seed_variation:
        user_content = _seed_user_message(prompt, seed_variation, lock_key, lock_tempo)
    else:
        user_content = _user_message(prompt, lock_key, lock_tempo)
    messages = [{"role": "user", "content": user_content}]

    buffer = ""
    meta_sent = False
    emitted_ids: set = set()

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            buffer += text

            if not meta_sent:
                meta_match = re.search(
                    r'"instrument"\s*:\s*"([^"]+)".*?"gm_patch"\s*:\s*(\d+).*?"is_drums"\s*:\s*(true|false)',
                    buffer, re.DOTALL
                )
                if not meta_match:
                    # Only fall back to partial match once we've seen "variations" —
                    # meaning is_drums won't appear later (it comes before variations in the schema).
                    # This prevents mis-detecting drums when gm_patch arrives but is_drums hasn't yet.
                    if '"variations"' in buffer:
                        meta_match = re.search(
                            r'"instrument"\s*:\s*"([^"]+)".*?"gm_patch"\s*:\s*(\d+)',
                            buffer, re.DOTALL
                        )
                        if meta_match:
                            instr_lower = meta_match.group(1).lower()
                            is_drums = any(w in instr_lower for w in [
                                "drum", "percussion", "beat",
                                "808", "909", "606", "707", "cr-78", "linn", "tr-",
                            ])
                            yield {
                                "type": "meta",
                                "instrument": meta_match.group(1),
                                "gm_patch": int(meta_match.group(2)),
                                "is_drums": is_drums,
                            }
                            meta_sent = True
                else:
                    yield {
                        "type": "meta",
                        "instrument": meta_match.group(1),
                        "gm_patch": int(meta_match.group(2)),
                        "is_drums": meta_match.group(3) == "true",
                    }
                    meta_sent = True

            for match in re.finditer(
                r'\{\s*"id"\s*:\s*(\d+).*?"notes"\s*:\s*\[.*?\]\s*\}', buffer, re.DOTALL
            ):
                vid = int(match.group(1))
                if vid not in emitted_ids:
                    try:
                        var = json.loads(match.group(0))
                        emitted_ids.add(vid)
                        yield {"type": "variation", "variation": var}
                    except json.JSONDecodeError:
                        pass

    yield {"type": "done", "prompt": prompt}
