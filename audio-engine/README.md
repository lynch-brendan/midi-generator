# Nasty Audio Engine

Native C++ subprocess that hosts VST3/AU/CLAP plugins and drives the audio device.
Electron talks to it over a local WebSocket. This is the piece that unlocks
"load Serum, load Sytrus, load Auto-Tune."

## Why a separate process (not inside Electron)

- **Audio has to be real-time.** The audio callback needs to run every ~5 ms
  without stalls. Chromium/Node's garbage collector and JS event loop can freeze
  for tens of ms. A native process gets a dedicated real-time audio thread.
- **Plugins can crash.** A misbehaving VST shouldn't take down the whole DAW.
  If the audio engine crashes, Electron respawns it and the UI keeps working.
- **License isolation.** Plugin binaries load into the audio process; the UI
  process stays clean.

## The tech choice — JUCE

JUCE is the industry-standard C++ framework for audio work — MIT-licensed for
open source, used by most commercial plugin/host developers. It ships:

- `AudioPluginFormatManager` — scans and instantiates VST3/AU/AAX/LV2/CLAP
- `AudioProcessorGraph` — patches plugins together with audio routing
- `AudioDeviceManager` — talks to CoreAudio/WASAPI/ASIO/JACK
- Reference example: JUCE ships `AudioPluginHost/` — a working plugin host
  we can lift patterns from directly.

Alternatives considered:
- **CLAP host (clap-host)** — cleaner API but only hosts CLAP-format plugins
  (small ecosystem still). Would exclude most existing VST3 libraries.
- **Roll our own** — months of work reimplementing what JUCE already provides.
- **iPlug2** — similar to JUCE, smaller community.

## Architecture

```
┌───────────────────────────────┐     WebSocket JSON     ┌────────────────────────────┐
│                               │◄──────────────────────►│                            │
│  Electron (nasty.html + JS)   │    localhost:37173     │   nasty-audio-engine       │
│  - UI, song state, sequencer  │                        │   - JUCE plugin host       │
│  - Web Audio for previews     │                        │   - AudioDeviceManager     │
│  - Sends: load plugin, note on│                        │   - Real-time audio thread │
│  - Receives: plugin list, ...│                        │   - Renders to output       │
└───────────────────────────────┘                        └────────────────────────────┘
```

**Message shapes (draft):**

Electron → engine:
- `{cmd:"scan_plugins", paths:[...]}` — enumerate installed plugins
- `{cmd:"load_plugin", channelId:"...", pluginId:"..."}` — instantiate
- `{cmd:"unload_plugin", channelId:"..."}` 
- `{cmd:"set_param", channelId:"...", paramId:..., value:...}`
- `{cmd:"note_on", channelId:"...", pitch:60, velocity:0.8, atSample:...}`
- `{cmd:"note_off", channelId:"...", pitch:60, atSample:...}`
- `{cmd:"transport", playing:true, bpm:120, startBar:0}`
- `{cmd:"set_channel_gain", channelId:"...", gain:0.8}`

Engine → Electron:
- `{event:"plugin_list", plugins:[{id, name, format, category, ...}]}`
- `{event:"plugin_loaded", channelId, params:[...]}`
- `{event:"level", channelId, dbfs:...}` — for meter animation
- `{event:"error", message:"..."}`

**Audio flow:**

The engine owns the output device. Each Nasty channel with a plugin becomes an
`AudioProcessorGraph` node routed to the master output. Channels without
plugins can still be handled by Electron's Web Audio synths — the two systems
sum acoustically through the OS mixer (fine for MVP; later we route Web Audio
into the engine too for unified mixing).

## Build (once JUCE is available)

The project uses CMake. Two ways to bring in JUCE:

**Option A — as a git submodule (recommended):**
```sh
cd audio-engine
git submodule add https://github.com/juce-framework/JUCE.git juce
git submodule update --init --recursive
mkdir build && cd build
cmake .. -G Xcode              # macOS
# or: cmake .. -G "Visual Studio 17 2022"   # Windows
cmake --build . --config Release
```

**Option B — system JUCE via Homebrew:**
```sh
brew install juce
# then in CMakeLists.txt use find_package(JUCE)
```

The output binary `nasty-audio-engine` gets bundled into the Electron app via
`extraResources` in `electron/package.json`.

## Current status

This directory contains **scaffolding, not a working engine yet.** What's here:
- `CMakeLists.txt` — starter build file (expects JUCE at `./juce`)
- `src/main.cpp` — entry point that opens the WebSocket
- `src/PluginHost.h/.cpp` — class skeleton
- `src/IpcServer.h/.cpp` — WebSocket wrapper
- Electron's `main.js` has a `startAudioEngine()` stub that will spawn this
  binary when it exists (silently no-ops today)

**Concrete next steps to get "load Serum" working:**
1. Add JUCE submodule and get the empty project building
2. Wire `AudioPluginFormatManager` scan → return plugin list via IPC
3. Load a plugin, print its parameters, close it
4. Open `AudioDeviceManager` default output; render a test tone through the
   loaded plugin
5. Wire MIDI note-on/note-off from Electron
6. Sync transport/BPM to the sequencer
7. Bundle the binary into the Electron `.dmg` and add codesigning
   entitlements for plugin loading
