# MIDI Generator

AI-powered musical idea generator. Type a prompt, get 5 MIDI + WAV variations back.

```bash
python3 generate.py "jazzy piano riff in D minor"
python3 generate.py "triumphant trumpet fanfare"
python3 generate.py "daft punk style bassline"
```

## Quick Start

```bash
# 1. Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 2. Run setup (installs FluidSynth + soundfont + Python deps)
bash setup.sh

# 3. Generate
python3 generate.py "sad piano melody"
```

Output lands in `output/<prompt-slug>/`:
- `01-the-bold-version.mid` + `.wav`
- `02-the-subtle-version.mid` + `.wav`
- ... (5 total)

## How It Works

1. **Claude API** generates 5 musically distinct note sequences as JSON
2. **`core/midi_writer.py`** converts JSON → binary MIDI (pure Python, no dependencies)
3. **`core/audio_renderer.py`** calls FluidSynth to render MIDI → WAV using a GM soundfont

## Project Structure

```
midi-generator/
├── generate.py           # CLI entry point
├── requirements.txt      # anthropic SDK only
├── setup.sh              # installs FluidSynth + soundfont
├── core/
│   ├── claude_client.py  # Claude API + prompt caching
│   ├── midi_writer.py    # pure Python MIDI binary writer
│   ├── audio_renderer.py # FluidSynth subprocess wrapper
│   └── variations.py     # validation + sanitization helpers
├── prompts/
│   └── system_prompt.txt # music theory constraints for Claude
├── output/               # generated files land here
└── web/                  # future Next.js frontend
```

## Requirements

- Python 3.8+
- `anthropic` pip package
- FluidSynth (for audio — MIDI works without it)
- A GM SF2 soundfont (setup.sh downloads GeneralUser GS)

## Adding a Frontend

The `web/` directory is reserved for a Next.js app. The `generate.py` logic will become an API route that streams results back to the browser.
