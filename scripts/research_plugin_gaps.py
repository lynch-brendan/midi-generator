"""
Batched plugin-knowledge research.

Reads the server-side gap log (plugins users have installed that we don't
have a cheatsheet for), asks Claude — with web search — to research each
one, and writes:

  1. A plugin sheet (execution layer) to plugin-knowledge/plugins/<slug>.md
     — params, presets, quirks. Same shape as before.
  2. Entries in the matching sound-goal sheets (discovery layer) under
     plugin-knowledge/sound-goals/{instruments,effects}/<Category>.md
     — character, best-for, emotional tags, comparisons, how-to-use.

This is Phase 2 of the two-layer cheatsheet system. Phase 1 (structure +
hand-written entries) shipped in b607c91. This script is how NEW plugins
get their entries generated automatically.

Runs on the maintainer's machine using the maintainer's ANTHROPIC_API_KEY.
Users are never charged. Users never see a prompt to contribute.

Usage:
    export ANTHROPIC_API_KEY=sk-...

    # Research plugins from a local gap-log file:
    python scripts/research_plugin_gaps.py --gap-log /tmp/nasty-plugin-gaps.jsonl

    # Or fetch from production:
    python scripts/research_plugin_gaps.py --from-server https://museaimusician.com

    # Or test on one specific plugin by name (skips gap log entirely):
    python scripts/research_plugin_gaps.py --plugin "Vital"

    # Options:
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


# The 20 sound-goal categories the researcher can place a plugin into.
# Kept in sync with the folder structure under plugin-knowledge/sound-goals/.
INSTRUMENT_CATEGORIES = [
    "Strings", "Keys", "Winds", "Bass", "Lead",
    "Pads", "Drums", "Vocal", "World", "Textures",
]
EFFECT_CATEGORIES = [
    "Reverbs", "Delays", "Modulation", "Compression", "EQ",
    "Saturation", "Stereo", "Pitch", "Filters", "Utility",
]


RESEARCH_PROMPT_TEMPLATE = """You are researching a VST3/AU audio plugin for
a two-layer plugin-knowledge registry used by an AI music assistant. There
are two output artifacts:

1) A **plugin sheet** (execution layer) — how to actually use this plugin:
   params, presets, quirks. Same as documentation.

2) **Sound-goal entries** (discovery layer) — how the AI matches a
   producer's musical intent ("give me a warm dark bass") to this plugin.
   Each entry has character/vibe/genre/comparison tags. One entry per
   sound-goal category the plugin belongs in. A synth like Surge XT can
   go in multiple instrument categories (Bass + Lead + Pad). An effect
   like Valhalla Supermassive typically goes in ONE effect category.

Plugin to research:
- Name: {name}
- Manufacturer: {manufacturer}
- Format: {format}
- Is instrument (vs effect): {is_instrument}

Search the web for this plugin's official docs, reviews, YouTube demo
descriptions, and forum discussions. Extract:
- Params/presets/quirks (for the plugin sheet)
- Character/vibe/genre/comparisons (for sound-goal entries)

Be honest about what you don't know — better to omit a field than guess.
If the plugin doesn't fit any sound-goal category (e.g., a utility that
does nothing musically useful, or is explicitly not-for-use like FL Studio
VSTi hosted as a plugin), return an empty category_entries array.

Available sound-goal categories:
- Instrument categories: {instrument_cats}
- Effect categories: {effect_cats}

Return ONLY a JSON object matching this schema. No preamble, no explanation,
no markdown fences around the JSON:

{{
  "plugin_sheet": "<full markdown of the plugin sheet, INCLUDING frontmatter with name, verified: false, last_updated: {today}, and preset_paths if you have HIGH confidence>",
  "category_entries": [
    {{
      "category": "<exact category name from the lists above>",
      "type": "instrument" | "effect",
      "entry_markdown": "<the markdown block to insert into that sound-goal sheet, starting with '### {name}' as the H3 header, followed by Character/Best for/Emotional tags/Comparison/How to use fields>"
    }}
  ]
}}

Plugin sheet skeleton (fill in what you find, omit sections you can't verify):

---
name: {name}
verified: false
last_updated: {today}
preset_paths:
  - "<macOS or Windows path>:<extension>"
  # Include ONLY if you have HIGH confidence in the path. Format is
  # <dir>:<file-extension>, one directory per entry. The client scans
  # recursively. Use ~ for the user's home directory. Omit entirely
  # if you don't know or the plugin doesn't have file-based presets.
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

Sound-goal entry format (one per category the plugin belongs in):

### {name}

- **Character:** <warm/aggressive/gritty/ethereal/etc — what does it SOUND like>
- **Best for:** <the use cases this plugin excels at in this category>
- **Emotional tags:** <mood/vibe descriptors — dreamy, tense, uplifting, etc>
- **Comparison:** <compared to other options in this category — warmer than X, more aggressive than Y>
- **How to use:** <exact tool call format, e.g. `load_instrument(channel_id=..., plugin_id="<{name} id>", preset_name="...")` or `add_plugin_effect(...)`>

Return ONLY the JSON object. No prose."""


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-") or "plugin"


def existing_plugin_names(plugin_sheets_dir: Path) -> set[str]:
    """Names of plugins that already have an execution-layer sheet."""
    names = set()
    if not plugin_sheets_dir.is_dir():
        return names
    for md in plugin_sheets_dir.glob("*.md"):
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


def _extract_json_from_text(text: str) -> dict:
    """Claude sometimes wraps JSON in ```json fences or adds preamble.
    Pull out the JSON object robustly. Raises on unparseable output."""
    # 1) Try any ```json fence.
    fence_m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fence_m:
        candidate = fence_m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # 2) Find the first `{` and last `}` — greedy but usually works when
    #    there's preamble/postamble text.
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        candidate = text[first : last + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # 3) Last resort — the whole thing.
    return json.loads(text.strip())


def _sanitize_plugin_sheet(md: str, name: str, today: str) -> str:
    """Strip stray fences and ensure a frontmatter block. The plugin sheet
    is markdown that Claude might have wrapped in an outer fence when it
    generated the JSON blob."""
    fence_m = re.search(r"```(?:markdown|md)?\s*\n(.*?)```", md, re.DOTALL)
    if fence_m:
        md = fence_m.group(1)
    idx = md.find("---")
    if idx > 0:
        md = md[idx:]
    md = md.strip() + "\n"
    if not md.startswith("---"):
        md = f"---\nname: {name}\nverified: false\nlast_updated: {today}\n---\n\n" + md
    return md


def _find_sound_goal_path(sound_goals_dir: Path, category: str, category_type: str) -> Path | None:
    """Resolve category name + type to an existing sound-goal sheet path.
    Case-insensitive on category name to be forgiving of model output."""
    subdir = "instruments" if category_type == "instrument" else "effects"
    parent = sound_goals_dir / subdir
    if not parent.is_dir():
        return None
    target_lower = category.lower()
    for md in parent.glob("*.md"):
        if md.stem.lower() == target_lower:
            return md
    return None


def _upsert_sound_goal_entry(sheet_path: Path, plugin_name: str, entry_markdown: str) -> str:
    """Add or replace this plugin's entry in a sound-goal sheet.

    - If a `### {plugin_name}` H3 already exists, replace its whole section
      (from that heading up to the next `### ` or `## ` heading).
    - Otherwise, append the entry under the `## Options` section (or at the
      end of the file if no Options section exists — fallback).

    Returns a short human-readable status ("added" / "replaced")."""
    text = sheet_path.read_text(encoding="utf-8")

    # Look for an existing `### <plugin_name>` heading (case-insensitive
    # on the plugin name — the full line may have suffixes like em-dash).
    name_re = re.compile(
        rf"^###\s+{re.escape(plugin_name)}(\s|$|\W)",
        re.IGNORECASE | re.MULTILINE,
    )
    start_match = name_re.search(text)

    # Normalize the entry: ensure it starts with `### {plugin_name}` and
    # ends with a single blank-line separator.
    entry = entry_markdown.strip()
    if not entry.startswith("### "):
        # If the model returned a body without the heading, add one.
        entry = f"### {plugin_name}\n\n{entry}"
    if not entry.endswith("\n"):
        entry += "\n"
    entry_block = entry + "\n"

    if start_match:
        # Find the end of the existing section: next `### ` or `## ` line.
        rest = text[start_match.end():]
        end_relative = re.search(r"^(###\s|##\s)", rest, re.MULTILINE)
        end_abs = start_match.end() + end_relative.start() if end_relative else len(text)
        new_text = text[: start_match.start()] + entry_block + text[end_abs:]
        sheet_path.write_text(new_text, encoding="utf-8")
        return "replaced"

    # Insert under `## Options` if present.
    options_match = re.search(r"^##\s+Options\s*$", text, re.MULTILINE)
    if options_match:
        # Insert after the Options heading + any blank line following.
        insert_at = options_match.end()
        # Skip a following blank line so the entry sits directly under
        # "## Options" with one blank between.
        after = text[insert_at:]
        blank = re.match(r"\n+", after)
        if blank:
            insert_at += blank.end()
        new_text = text[:insert_at] + entry_block + text[insert_at:]
        sheet_path.write_text(new_text, encoding="utf-8")
        return "added"

    # Fallback: append at the end of the file.
    sep = "" if text.endswith("\n") else "\n"
    sheet_path.write_text(text + sep + "\n" + entry_block, encoding="utf-8")
    return "appended (no Options section found)"


def research_one(client: Anthropic, entry: dict, today: str) -> dict:
    prompt = RESEARCH_PROMPT_TEMPLATE.format(
        name=entry.get("name", ""),
        manufacturer=entry.get("manufacturer", "") or "unknown",
        format=entry.get("format", "") or "unknown",
        is_instrument=str(entry.get("is_instrument", "unknown")),
        today=today,
        instrument_cats=", ".join(INSTRUMENT_CATEGORIES),
        effect_cats=", ".join(EFFECT_CATEGORIES),
    )
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": prompt}],
    )
    chunks = []
    for block in resp.content:
        if getattr(block, "type", "") == "text":
            chunks.append(block.text)
    raw = "".join(chunks).strip()
    return _extract_json_from_text(raw)


def apply_research(
    result: dict,
    plugin_name: str,
    today: str,
    plugin_sheets_dir: Path,
    sound_goals_dir: Path,
) -> list[str]:
    """Write the researched plugin sheet + sound-goal entries to disk.
    Returns a list of status lines for logging."""
    statuses: list[str] = []

    # 1) Plugin sheet.
    plugin_md = _sanitize_plugin_sheet(result.get("plugin_sheet", ""), plugin_name, today)
    slug = slugify(plugin_name)
    plugin_sheets_dir.mkdir(parents=True, exist_ok=True)
    target = plugin_sheets_dir / f"{slug}.md"
    target.write_text(plugin_md, encoding="utf-8")
    statuses.append(f"  plugin sheet -> {target.relative_to(plugin_sheets_dir.parent.parent)}")

    # 2) Sound-goal entries.
    entries = result.get("category_entries") or []
    if not entries:
        statuses.append("  no sound-goal categories (plugin has no musical placement)")
        return statuses

    for entry in entries:
        category = (entry.get("category") or "").strip()
        cat_type = (entry.get("type") or "").strip().lower()
        entry_md = entry.get("entry_markdown") or ""
        if not category or not cat_type or not entry_md:
            statuses.append(f"  skipped malformed entry: {entry}")
            continue

        sheet_path = _find_sound_goal_path(sound_goals_dir, category, cat_type)
        if not sheet_path:
            statuses.append(f"  skipped unknown category: {category} ({cat_type})")
            continue

        status = _upsert_sound_goal_entry(sheet_path, plugin_name, entry_md)
        rel = sheet_path.relative_to(sound_goals_dir.parent.parent)
        statuses.append(f"  sound-goal -> {rel} ({status})")

    return statuses


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap-log", type=Path, default=Path("/tmp/nasty-plugin-gaps.jsonl"))
    ap.add_argument("--from-server", type=str, default="",
                    help="Fetch gaps from a running Nasty server (e.g. https://museaimusician.com)")
    ap.add_argument("--plugin", type=str, default="",
                    help="Research this ONE plugin by name — skips gap log entirely. Useful for testing.")
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parent.parent / "plugin-knowledge")
    ap.add_argument("--top", type=int, default=0, help="Only research the N most-missed plugins (0 = all)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plugin_sheets_dir = args.out / "plugins"
    sound_goals_dir = args.out / "sound-goals"

    if not args.out.is_dir():
        print(f"out dir does not exist: {args.out}", file=sys.stderr)
        return 1
    if not sound_goals_dir.is_dir():
        print(f"sound-goals dir does not exist: {sound_goals_dir} — "
              "run the Phase 1 restructure first", file=sys.stderr)
        return 1

    from datetime import date
    today = str(date.today())

    # --plugin flag: skip the gap-log entirely, research one plugin by name.
    if args.plugin:
        one = {
            "name": args.plugin,
            "manufacturer": "",
            "format": "",
            "is_instrument": "unknown",
        }
        entries_to_research = [(1, one)]
        stale = []
    else:
        # Normal path: read the gap log.
        if args.from_server:
            import urllib.request
            url = args.from_server.rstrip("/") + "/nasty/plugin-gaps"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "nasty-research-script/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
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

        have = existing_plugin_names(plugin_sheets_dir)
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

        entries_to_research = fresh

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
        print(f"\n{'RE-researching (stale)' if replacing else 'researching'}: "
              f"{name} ({count} report(s))...")
        try:
            result = research_one(client, e, today)
        except Exception as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            return
        try:
            statuses = apply_research(result, name, today,
                                      plugin_sheets_dir, sound_goals_dir)
        except Exception as exc:
            print(f"  FAILED to apply research: {exc}", file=sys.stderr)
            return
        for s in statuses:
            print(s)

    for count, e in stale:
        do_one(count, e, replacing=True)
    for count, e in entries_to_research:
        do_one(count, e, replacing=False)

    print("\ndone. review the new/updated files, edit as needed, then commit + push.")
    print("railway autodeploys → users get the fresh cheatsheets on their next chat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
