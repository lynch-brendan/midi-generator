"""
Claude API client for music generation.
Uses prompt caching on the system prompt to reduce costs on repeated calls.
"""
import json
import re
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

    user_message = (
        f'Generate 5 musical variations for: "{prompt}"\n\n'
        "Choose the most appropriate instrument and key for this style. "
        "Return the complete JSON object with all 5 variations, each with a full note sequence. "
        "Aim for 12-24 notes per variation so each feels like a complete musical idea. "
        "Remember: return ONLY raw JSON, no markdown."
    )

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


def _user_message(prompt: str) -> str:
    return (
        f'Generate 5 musical variations for: "{prompt}"\n\n'
        "Choose the most appropriate instrument and key for this style. "
        "Return the complete JSON object with all 5 variations, each with a full note sequence. "
        "Aim for 12-24 notes per variation so each feels like a complete musical idea. "
        "Remember: return ONLY raw JSON, no markdown."
    )


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
