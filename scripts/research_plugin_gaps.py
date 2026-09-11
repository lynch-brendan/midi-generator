"""
Batched plugin-knowledge research.

Reads the server-side gap log (plugins users have installed that we don't
have a cheatsheet for), asks Claude — with web search — to research each
one, and writes a starter cheatsheet to plugin-knowledge/<slug>.md.

Runs on the maintainer's machine using the maintainer's ANTHROPIC_API_KEY.
Users are never charged. Users never see a prompt to contribute.

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python scripts/research_plugin_gaps.py \\
        --gap-log /path/to/nasty-plugin-gaps.jsonl \\
        --out plugin-knowledge/ \\
        --top 10          # only research the N most-frequently-missed
        --dry-run         # print what would happen, don't call Claude

Entries are written with `verified: false` frontmatter — you review, edit,
commit. Once you commit + Railway redeploys, every affected user gets the
new cheatsheets automatically on their next chat.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    print("pip install anthropic", file=sys.stderr)
    sys.exit(1)


RESEARCH_PROMPT_TEMPLATE = """You are researching a VST3/AU audio plugin for
inclusion in a community-maintained plugin-knowledge registry. The registry
tells an AI music assistant how to reach into plugins that hide their real
patch browsers inside their own GUI (Surge XT, Serato Sample, etc.).

Plugin to research:
- Name: {name}
- Manufacturer: {manufacturer}
- Format: {format}
- Is instrument (vs effect): {is_instrument}

Search the web for this plugin's official docs or reliable community info
and write a markdown cheatsheet. Be honest about what you don't know —
better to omit a section than guess wrong.

Output ONLY the markdown file, starting with the frontmatter. No preamble.

Required frontmatter:
---
name: {name}
verified: false
last_updated: {today}
preset_paths:
  - "<macOS or Windows path>:<extension>"
  # Include ONLY if you have HIGH confidence in the path. Format is
  # <dir>:<file-extension>, one directory per entry. The client scans
  # recursively. Use ~ for the user's home directory. Omit entirely if
  # you don't know or the plugin doesn't have file-based presets.
---

# {name}

<one-line description>

## Presets on disk
<or "Not applicable — this plugin exposes presets via the standard VST/AU
program API." if standard API is authoritative>
<or "Not applicable — no factory preset library." for samplers etc.>

## Notable parameters
<3-6 most important knobs, name matches how the plugin exposes them>

## Quirks
<anything that would trip up an AI trying to automate this plugin —
e.g. "silent until a sample is loaded", "default patch is a placeholder">

## Common recipes (optional)
<bass/lead/pad quick recipes if the plugin is a synth and you know them>

Return only the markdown."""


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-") or "plugin"


def existing_slugs(out_dir: Path) -> set[str]:
    return {p.stem.lower() for p in out_dir.glob("*.md") if p.stem.lower() != "readme"}


def existing_names(out_dir: Path) -> set[str]:
    names = set()
    for md in out_dir.glob("*.md"):
        if md.stem.lower() == "readme":
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except Exception:
            continue
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        name_match = re.search(r"^name:\s*(.+)$", m.group(1), re.MULTILINE)
        if name_match:
            names.add(name_match.group(1).strip().lower())
    return names


def read_gap_log(path: Path) -> list[dict]:
    entries: list[dict] = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries


def rank_gaps(entries: list[dict], have_names: set[str]) -> tuple[list[tuple[int, dict]], list[tuple[int, dict]]]:
    """Split into (fresh_gaps, stale_entries).

    fresh_gaps = plugins not in have_names.
    stale_entries = plugins that ARE in have_names but have `stale: true`
                    reports — cheatsheet exists but its claims turned out
                    to be wrong on real machines, so we should re-research.
    """
    missing_counter: Counter[str] = Counter()
    missing_canonical: dict[str, dict] = {}
    stale_counter: Counter[str] = Counter()
    stale_canonical: dict[str, dict] = {}
    for e in entries:
        name = (e.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if e.get("stale") and key in have_names:
            stale_counter[name] += 1
            if name not in stale_canonical:
                stale_canonical[name] = e
        elif key not in have_names:
            missing_counter[name] += 1
            if name not in missing_canonical:
                missing_canonical[name] = e
    missing = [(missing_counter[n], missing_canonical[n]) for n, _ in missing_counter.most_common()]
    stale = [(stale_counter[n], stale_canonical[n]) for n, _ in stale_counter.most_common()]
    return missing, stale


def research_one(client: Anthropic, entry: dict, today: str) -> str:
    prompt = RESEARCH_PROMPT_TEMPLATE.format(
        name=entry.get("name", ""),
        manufacturer=entry.get("manufacturer", "") or "unknown",
        format=entry.get("format", "") or "unknown",
        is_instrument=str(entry.get("is_instrument", "unknown")),
        today=today,
    )
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": prompt}],
    )
    # Concatenate all text blocks from the response.
    chunks = []
    for block in resp.content:
        if getattr(block, "type", "") == "text":
            chunks.append(block.text)
    return "".join(chunks).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap-log", type=Path, default=Path("/tmp/nasty-plugin-gaps.jsonl"))
    ap.add_argument("--from-server", type=str, default="",
                    help="Fetch gaps from a running Nasty server (e.g. https://museaimusician.com) instead of a local file")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "plugin-knowledge")
    ap.add_argument("--top", type=int, default=0, help="Only research the N most-missed plugins (0 = all)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.out.is_dir():
        print(f"out dir does not exist: {args.out}", file=sys.stderr)
        return 1

    from datetime import date
    today = str(date.today())

    if args.from_server:
        import urllib.request
        url = args.from_server.rstrip("/") + "/nasty/plugin-gaps"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            entries = data.get("entries", [])
        except Exception as exc:
            print(f"failed to fetch {url}: {exc}", file=sys.stderr)
            return 1
        if not entries:
            print(f"no gaps returned from {url}")
            return 0
    else:
        entries = read_gap_log(args.gap_log)
        if not entries:
            print(f"no gaps logged at {args.gap_log}")
            return 0

    have = existing_names(args.out)
    fresh, stale = rank_gaps(entries, have)
    if args.top > 0:
        fresh = fresh[: args.top]
        stale = stale[: args.top]

    if not fresh and not stale:
        print("no missing plugins and no stale cheatsheets — nothing to do")
        return 0

    if fresh:
        print(f"\nMISSING cheatsheets ({len(fresh)}):")
        for count, e in fresh:
            print(f"  {count:3d}× {e.get('name')}  ({e.get('manufacturer') or 'unknown mfg'})")
    if stale:
        print(f"\nSTALE cheatsheets to REPLACE ({len(stale)}):")
        for count, e in stale:
            print(f"  {count:3d}× {e.get('name')}  ({e.get('manufacturer') or 'unknown mfg'})  — {e.get('reason', '')}")

    if args.dry_run:
        print("\n(dry-run — no API calls made)")
        return 0

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    client = Anthropic(api_key=api_key)

    def do_one(count: int, e: dict, replacing: bool) -> None:
        name = e.get("name", "")
        slug = slugify(name)
        target = args.out / f"{slug}.md"
        # For fresh gaps, skip if a file (perhaps with a different slug) already
        # exists for this name. For stale, we EXPECT a file to exist and are
        # replacing it, so we don't skip.
        if not replacing:
            if target.exists():
                print(f"skip {name}: {target.name} already exists")
                return
        print(f"\n{'RE-researching (stale)' if replacing else 'researching'}: {name} ({count} report(s))...")
        try:
            md = research_one(client, e, today)
        except Exception as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            return
        if not md.startswith("---"):
            md = f"---\nname: {name}\nverified: false\nlast_updated: {today}\n---\n\n" + md
        target.write_text(md, encoding="utf-8")
        print(f"  wrote {target}")

    for count, e in stale:
        do_one(count, e, replacing=True)
    for count, e in fresh:
        do_one(count, e, replacing=False)

    print("\ndone. review the new/replaced files, edit as needed, then commit + push.")
    print("railway autodeploys → users get the fresh cheatsheets on their next chat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
