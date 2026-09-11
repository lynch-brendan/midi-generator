# Nasty Plugin Knowledge

Community-curated cheatsheets for VST3/AU plugins. Each `.md` file describes
one plugin — where its presets live on disk, notable parameters, quirks.

Nasty pulls these into Claude's chat context so it knows how to reach into
plugins that hide their patch browsers inside their own GUI (Surge XT,
Serato Sample, etc.) instead of exposing them through the standard VST3/AU
program API.

## File format

```markdown
---
name: <plugin name — must match manifest name, case-insensitive>
verified: true | false
last_updated: YYYY-MM-DD
---

# Plugin Name

One-line description.

## Presets on disk (optional)

## Notable parameters (optional)

## Quirks (optional)

## Common recipes (optional)
```

## What NOT to put here

- Opinion or musical taste — that's Claude's job.
- Anything that changes per user (their personal patches, etc.).
- Anything that isn't factually stable — this is a shared registry.

## Contributing

Add or improve a plugin entry, open a PR. Verified entries get merged fast.
