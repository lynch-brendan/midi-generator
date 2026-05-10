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
MAX_TOKENS = 8096
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


def _user_message(prompt: str) -> str:
    angle = random.choice(_CREATIVE_ANGLES)
    return (
        f'Generate 5 musical variations for: "{prompt}"\n\n'
        f"Creative direction for this session: {angle}\n\n"
        "Choose the most appropriate instrument and key for this style. "
        "Return the complete JSON object with all 5 variations, each with a full note sequence. "
        "Aim for 12-24 notes per variation so each feels like a complete musical idea. "
        "Remember: return ONLY raw JSON, no markdown."
    )


VARIATION_ANGLES = random.sample(_CREATIVE_ANGLES, min(5, len(_CREATIVE_ANGLES)))


def generate_single_variation(prompt: str, creative_direction: str, variation_number: int) -> Dict[str, Any]:
    """Generate one variation with a specific creative direction. Returns parsed dict."""
    client = anthropic.Anthropic()
    system_prompt = _load_system_prompt()

    user_content = (
        f'Generate exactly 1 musical variation for: "{prompt}"\n\n'
        f"Creative direction: {creative_direction}\n\n"
        "Pick the most appropriate instrument and key for this prompt and direction. "
        "Return a JSON object with this exact schema — ONE variation only:\n"
        "{\n"
        '  "instrument": "<chosen instrument>",\n'
        '  "gm_patch": <0-127>,\n'
        '  "is_drums": <true|false>,\n'
        '  "key": "<key name>",\n'
        '  "scale_notes": ["<note names>"],\n'
        '  "variation": {\n'
        f'    "id": {variation_number + 1},\n'
        '    "name": "<evocative name>",\n'
        '    "character": "<one sentence>",\n'
        '    "tempo": <BPM>,\n'
        '    "expression": "<none|subtle|moderate|expressive>",\n'
        '    "notes": [{"pitch": <0-127>, "duration": <beats>, "velocity": <1-127>, "time": <beats>}]\n'
        "  }\n"
        "}\n\n"
        "Aim for 16-28 notes. Return ONLY raw JSON, no markdown."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = ""
    for block in response.content:
        if block.type == "text":
            raw_text = block.text
            break

    if not raw_text:
        raise ValueError("Empty response from Claude")

    clean = _extract_json(raw_text)
    data = json.loads(clean)

    if "variation" not in data:
        raise ValueError(f"Response missing 'variation' key. Keys: {list(data.keys())}")

    return data


def stream_thinking(prompt: str) -> Generator[Dict, None, None]:
    """Stream a brief 'thinking out loud' narrative before generation starts."""
    client = anthropic.Anthropic()
    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        messages=[{
            "role": "user",
            "content": (
                f'You\'re a creative musician. Someone asked you for: "{prompt}". '
                "Think out loud in 1-2 casual sentences about what musical ideas, "
                "artists, or feelings immediately come to mind. Be specific and vivid — "
                "mention real artists, eras, or techniques. No lists, no punctuation at the start, just flowing thought."
            ),
        }],
    ) as stream:
        for text in stream.text_stream:
            yield {"type": "thought", "token": text}


def stream_variations(prompt: str) -> Generator[Dict, None, None]:
    """
    Stream Claude's response and yield parsed objects as they become available.
    Yields: one 'meta' dict first, then one 'variation' dict per variation, then 'done'.
    """
    client = anthropic.Anthropic()
    system_prompt = _load_system_prompt()

    buffer = ""
    meta_sent = False
    emitted_ids: set = set()

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": _user_message(prompt)}],
    ) as stream:
        for text in stream.text_stream:
            buffer += text

            if not meta_sent:
                meta_match = re.search(
                    r'"instrument"\s*:\s*"([^"]+)".*?"gm_patch"\s*:\s*(\d+).*?"is_drums"\s*:\s*(true|false).*?"key"\s*:\s*"([^"]+)"',
                    buffer, re.DOTALL
                )
                if not meta_match:
                    meta_match = re.search(
                        r'"instrument"\s*:\s*"([^"]+)".*?"gm_patch"\s*:\s*(\d+).*?"key"\s*:\s*"([^"]+)"',
                        buffer, re.DOTALL
                    )
                    if meta_match:
                        is_drums = any(w in meta_match.group(1).lower() for w in ["drum", "percussion", "beat"])
                        yield {
                            "type": "meta",
                            "instrument": meta_match.group(1),
                            "gm_patch": int(meta_match.group(2)),
                            "key": meta_match.group(3),
                            "is_drums": is_drums,
                        }
                        meta_sent = True
                else:
                    yield {
                        "type": "meta",
                        "instrument": meta_match.group(1),
                        "gm_patch": int(meta_match.group(2)),
                        "is_drums": meta_match.group(3) == "true",
                        "key": meta_match.group(4),
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
