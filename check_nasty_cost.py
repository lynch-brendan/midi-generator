#!/usr/bin/env python3
"""Diagnose Nasty chat cost by reading the last N turns from nasty_chat_logs.

Prints per-turn cost, cache hit rate, and song-state size so we can see
what's actually blowing tokens — instead of guessing.

Usage:
    export DATABASE_URL=postgresql://...
    python check_nasty_cost.py           # last 20 turns
    python check_nasty_cost.py 50        # last 50 turns
"""
import json
import os
import sys

# Load a .env if present so DATABASE_URL comes through without manual export.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from core.db import SessionLocal
from core.models import NastyChatLog

# Sonnet 4.6 pricing per 1M tokens.
PRICE_INPUT = 3.00
PRICE_OUTPUT = 15.00
PRICE_CACHE_READ = 0.30
PRICE_CACHE_WRITE = 3.75


def cost_usd(inp: int, out: int, cread: int, cwrite: int) -> float:
    return (
        inp * PRICE_INPUT
        + out * PRICE_OUTPUT
        + cread * PRICE_CACHE_READ
        + cwrite * PRICE_CACHE_WRITE
    ) / 1_000_000


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20

    if SessionLocal is None:
        print("ERROR: DATABASE_URL not set. Export it (Railway → Variables) or add to .env.")
        sys.exit(1)

    with SessionLocal() as db:
        rows = (
            db.query(NastyChatLog)
              .order_by(NastyChatLog.created_at.desc())
              .limit(limit)
              .all()
        )

    if not rows:
        print("No rows in nasty_chat_logs yet.")
        return

    rows = list(reversed(rows))  # oldest first, so you read top-to-bottom in time order

    header = (
        f"{'when':>14}  {'$cost':>8}  {'in':>7}  {'c_read':>8}  {'c_write':>8}  "
        f"{'hit%':>5}  {'out':>6}  {'tools':>5}  {'song_kB':>7}  msg"
    )
    print(header)
    print("-" * len(header))

    total_cost = 0.0
    total_in = 0
    total_cread = 0
    total_cwrite = 0
    total_out = 0
    max_tools_seen = 0

    for r in rows:
        inp = r.input_tokens or 0
        out = r.output_tokens or 0
        cread = r.cache_read_tokens or 0
        cwrite = r.cache_write_tokens or 0
        c = cost_usd(inp, out, cread, cwrite)

        denom = inp + cread + cwrite
        hit = (cread / denom * 100) if denom else 0.0

        try:
            n_tools = len(json.loads(r.tool_calls_json or "[]"))
        except Exception:
            n_tools = 0
        max_tools_seen = max(max_tools_seen, n_tools)

        song_kb = len(r.song_state_json or "") / 1024
        msg = (r.user_message or "").strip().replace("\n", " ")[:40]

        try:
            when = r.created_at.astimezone().strftime("%m-%d %H:%M:%S")
        except Exception:
            when = ""

        print(
            f"{when:>14}  ${c:>7.4f}  {inp:>7}  {cread:>8}  {cwrite:>8}  "
            f"{hit:>4.0f}%  {out:>6}  {n_tools:>5}  {song_kb:>6.1f}  {msg}"
        )

        total_cost += c
        total_in += inp
        total_cread += cread
        total_cwrite += cwrite
        total_out += out

    n = len(rows)
    denom_tot = total_in + total_cread + total_cwrite
    overall_hit = (total_cread / denom_tot * 100) if denom_tot else 0
    avg_song_kb = sum(len(r.song_state_json or "") for r in rows) / n / 1024

    print("-" * len(header))
    print(
        f"\nTotals over last {n} turns:\n"
        f"  Total cost:      ${total_cost:.4f}\n"
        f"  Avg per turn:    ${total_cost / n:.4f}\n"
        f"  Cache hit rate:  {overall_hit:.1f}%\n"
        f"  Input tokens:    {total_in:,}\n"
        f"  Cache read:      {total_cread:,}\n"
        f"  Cache write:     {total_cwrite:,}\n"
        f"  Output tokens:   {total_out:,}\n"
        f"  Avg song state:  {avg_song_kb:.1f} kB\n"
    )

    print("Diagnostic hints:")
    if overall_hit < 30:
        print(f"  [!] Cache hit rate is LOW ({overall_hit:.0f}%). Caching is set up in code")
        print("      but not actually working. Likely cause: something in system_blocks or")
        print("      the tools list is changing per turn, invalidating the prefix.")
    elif overall_hit < 60:
        print(f"  [~] Cache hit rate is moderate ({overall_hit:.0f}%). Working but not fully —")
        print("      could be first-turn-in-session cold starts, or 5-min TTL expiring")
        print("      between messages when you pause to think.")
    else:
        print(f"  [ok] Cache hit rate is healthy ({overall_hit:.0f}%).")

    if avg_song_kb > 20:
        print(f"  [!] Average song_state is {avg_song_kb:.1f} kB — sent uncached every turn.")
        print("      Trimming song state (or caching it separately) is high-leverage.")
    elif avg_song_kb > 5:
        print(f"  [~] Song state avg {avg_song_kb:.1f} kB — moderate. Watchable.")

    if max_tools_seen >= 5:
        print(f"  [!] Some turns chained {max_tools_seen} tool calls in the loop. That's")
        print("      multiple API round-trips per user message. Loop caps at 6.")


if __name__ == "__main__":
    main()
