#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOUNDFONT_DIR="$SCRIPT_DIR/soundfonts"
SOUNDFONT_PATH="$SOUNDFONT_DIR/GeneralUser.sf2"
SOUNDFONT_URL="https://github.com/generalmidi/generalmidi/raw/master/GeneralUser_GS_1.471.sf2"
# Fallback: well-known direct download
SOUNDFONT_URL_ALT="https://archive.org/download/generaluser-gs-soundfont/GeneralUser_GS_v1.471.sf2"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  MIDI Generator — Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Python virtual environment ─────────────────────────────────────────
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo ""
    echo "→ Creating Python virtual environment..."
    python3 -m venv "$SCRIPT_DIR/.venv"
fi

echo "→ Installing Python dependencies..."
"$SCRIPT_DIR/.venv/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
echo "  ✓ Python dependencies installed"

# ── 2. FluidSynth ─────────────────────────────────────────────────────────
echo ""
echo "→ Checking for FluidSynth..."

if command -v fluidsynth &>/dev/null; then
    echo "  ✓ FluidSynth already installed: $(fluidsynth --version 2>&1 | head -1)"
else
    echo "  FluidSynth not found — installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &>/dev/null; then
            brew install fluidsynth
        else
            echo "  ERROR: Homebrew not found. Install from https://brew.sh then re-run setup.sh"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update -q && sudo apt-get install -y fluidsynth
    else
        echo "  ERROR: Unsupported OS '$OSTYPE'. Install FluidSynth manually."
        exit 1
    fi
    echo "  ✓ FluidSynth installed"
fi

# ── 3. Soundfont ──────────────────────────────────────────────────────────
echo ""
echo "→ Checking for SF2 soundfont..."
mkdir -p "$SOUNDFONT_DIR"

if [ -f "$SOUNDFONT_PATH" ]; then
    echo "  ✓ Soundfont already present: $SOUNDFONT_PATH"
else
    echo "  Downloading GeneralUser GS soundfont (~30 MB)..."
    if command -v curl &>/dev/null; then
        curl -L --progress-bar -o "$SOUNDFONT_PATH" "$SOUNDFONT_URL_ALT" || \
        curl -L --progress-bar -o "$SOUNDFONT_PATH" "$SOUNDFONT_URL"
    elif command -v wget &>/dev/null; then
        wget -q --show-progress -O "$SOUNDFONT_PATH" "$SOUNDFONT_URL_ALT" || \
        wget -q --show-progress -O "$SOUNDFONT_PATH" "$SOUNDFONT_URL"
    else
        echo "  ERROR: Neither curl nor wget found. Download manually:"
        echo "  $SOUNDFONT_URL_ALT"
        echo "  → save to: $SOUNDFONT_PATH"
        exit 1
    fi

    if [ -f "$SOUNDFONT_PATH" ]; then
        echo "  ✓ Soundfont downloaded: $SOUNDFONT_PATH"
    else
        echo "  ERROR: Soundfont download failed. Download manually from:"
        echo "  $SOUNDFONT_URL_ALT"
        exit 1
    fi
fi

# ── 4. Output directories ─────────────────────────────────────────────────
mkdir -p "$SCRIPT_DIR/output"

# ── 5. API key check ──────────────────────────────────────────────────────
echo ""
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "  ⚠  ANTHROPIC_API_KEY is not set."
    echo "     Add it to your shell profile:"
    echo '     export ANTHROPIC_API_KEY="sk-ant-..."'
else
    echo "  ✓ ANTHROPIC_API_KEY is set"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete! Try:"
echo ""
echo '  python3 generate.py "triumphant trumpet fanfare"'
echo '  python3 generate.py "jazzy piano riff in D minor"'
echo '  python3 generate.py "daft punk style bassline"'
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
