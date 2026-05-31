"""
One-shot: measure real token usage per Muse generation.
Runs N generations with varied prompts, reports per-call and average cost.

Usage: python scripts/measure_cost.py [N]
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from core.claude_client import _load_system_prompt, _user_message, MODEL, MAX_TOKENS

# Sonnet 4.6 pricing (USD per 1M tokens) — verify against console.anthropic.com
PRICE_SONNET_INPUT = 3.00
PRICE_SONNET_OUTPUT = 15.00
PRICE_SONNET_CACHE_WRITE = 3.75
PRICE_SONNET_CACHE_READ = 0.30

PRICE_HAIKU_INPUT = 1.00
PRICE_HAIKU_OUTPUT = 5.00

PROMPTS = [
    "boom bap drums kanye style",
    "jazz piano real happy",
    "dark synth bass at 90 bpm",
    "acoustic guitar pop chord progression",
    "funky bassline 100 bpm e minor",
]


def call_once(client, system_prompt, prompt, label):
    user_msg = _user_message(prompt)
    t0 = time.time()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_msg}],
    )
    elapsed = time.time() - t0
    u = response.usage
    input_tok = getattr(u, "input_tokens", 0) or 0
    output_tok = getattr(u, "output_tokens", 0) or 0
    cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0

    cost = (
        input_tok * PRICE_SONNET_INPUT / 1_000_000
        + output_tok * PRICE_SONNET_OUTPUT / 1_000_000
        + cache_read * PRICE_SONNET_CACHE_READ / 1_000_000
        + cache_write * PRICE_SONNET_CACHE_WRITE / 1_000_000
    )

    print(
        f"[{label}] '{prompt[:40]}' "
        f"input={input_tok} output={output_tok} "
        f"cache_read={cache_read} cache_write={cache_write} "
        f"cost=${cost:.4f} time={elapsed:.1f}s"
    )
    return {
        "input": input_tok,
        "output": output_tok,
        "cache_read": cache_read,
        "cache_write": cache_write,
        "cost": cost,
    }


def call_haiku_thinking(client, prompt):
    """Approximate the speech bubble cost."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=40,
        messages=[{
            "role": "user",
            "content": (
                f'A musician just got this request: "{prompt}". '
                "Write their ONE punchy reaction — 5-12 words, all lowercase, "
                "like a text message. No quotes, no period at the end."
            ),
        }],
    )
    u = response.usage
    input_tok = getattr(u, "input_tokens", 0) or 0
    output_tok = getattr(u, "output_tokens", 0) or 0
    cost = (
        input_tok * PRICE_HAIKU_INPUT / 1_000_000
        + output_tok * PRICE_HAIKU_OUTPUT / 1_000_000
    )
    return {"input": input_tok, "output": output_tok, "cost": cost}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    prompts = (PROMPTS * ((n // len(PROMPTS)) + 1))[:n]

    client = anthropic.Anthropic()
    system_prompt = _load_system_prompt()

    print(f"\nRunning {n} generations against {MODEL}...\n")

    results = []
    for i, p in enumerate(prompts, 1):
        label = "WARM" if i > 1 else "COLD"
        r = call_once(client, system_prompt, p, label)
        results.append(r)

    print("\nMeasuring Haiku speech bubble cost on one prompt...")
    haiku = call_haiku_thinking(client, prompts[0])
    print(f"  haiku input={haiku['input']} output={haiku['output']} cost=${haiku['cost']:.5f}")

    # Aggregate — separate cold and warm
    cold = results[0]
    warm = results[1:] if len(results) > 1 else []

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Cold (first) call cost (incl cache write): ${cold['cost']:.4f}")
    if warm:
        avg_warm = sum(r["cost"] for r in warm) / len(warm)
        avg_out = sum(r["output"] for r in warm) / len(warm)
        print(f"Warm avg cost (cache hit, n={len(warm)}):    ${avg_warm:.4f}")
        print(f"Warm avg output tokens:                    {avg_out:.0f}")
        print(f"+ Haiku speech bubble:                     ${haiku['cost']:.5f}")
        total_per_gen = avg_warm + haiku["cost"]
        print(f"\n=> Per generation (warm cache + haiku): ${total_per_gen:.4f}")
        print(f"   Creator tier (300 gen/mo) @ 50% usage:  ${total_per_gen * 150:.2f}")
        print(f"   Pro tier    (1000 gen/mo) @ 50% usage:  ${total_per_gen * 500:.2f}")
        print(f"   Creator tier @ 100% usage:              ${total_per_gen * 300:.2f}")
        print(f"   Pro tier    @ 100% usage:               ${total_per_gen * 1000:.2f}")


if __name__ == "__main__":
    main()
