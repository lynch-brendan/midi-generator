# Nasty Audio Engine

Native C++ subprocess that hosts VST3/AU plugins. Electron spawns it and
speaks JSON over stdin/stdout. Built on JUCE.

## What works today

- ✅ Builds on macOS (Xcode Command Line Tools + CMake)
- ✅ Scans the system's VST3 and AudioUnit folders on startup
- ✅ Reports every plugin found as JSON on stdout
- ✅ Loads a plugin instance into an `AudioProcessorGraph` node and wires
  it to the default audio output device on demand
- ✅ Piped to Electron: the desktop app's Browser dock shows a "Plugins"
  tab listing every discovered VST3/AU

## What doesn't work yet

- ❌ **MIDI note routing.** The engine accepts `note_on` / `note_off`
  messages but doesn't yet inject them into the plugin's audio callback.
  A proper impl needs a lock-free MIDI queue per plugin node. This is the
  next task if you want to actually hear the plugins play.
- ❌ **Plugin UIs.** Loading Serum's GUI window requires wiring
  `AudioProcessorEditor` into a native window and passing keyboard focus
  correctly. Not started.
- ❌ **Transport sync.** Play/stop from the DAW doesn't drive the plugin
  yet.
- ❌ **Codesigning.** Bundled `.dmg` will trigger "unknown developer"
  warnings.

## Build (once JUCE is fetched)

```sh
cd audio-engine
git submodule update --init --depth 1     # first time
mkdir -p build && cd build
cmake ..
cmake --build . --config Release          # ~3 min first time
```

Binary lands at `build/nasty-audio-engine_artefacts/nasty-audio-engine`.

## Run standalone (for debugging)

```sh
echo '{"cmd":"list_plugins"}' | ./build/nasty-audio-engine_artefacts/nasty-audio-engine
```

You'll see JSON lines: `{"event":"scanning","name":"..."}` while it
scans, then `{"event":"ready","plugins":N}` and then the list.

The Electron app does the same thing automatically — just launch the
desktop app and the plugin list appears in the Browser dock's "Plugins"
tab within a few seconds.

## Architecture

```
┌──────────────────────────┐  stdin JSON lines   ┌────────────────────────────┐
│  Electron (nasty.html)   │────────────────────►│                            │
│  - Browser dock UI       │                     │   nasty-audio-engine       │
│  - Sends: load_plugin,   │◄────────────────────│   - JUCE plugin host       │
│    note_on, set_param    │  stdout JSON lines  │   - AudioProcessorGraph    │
└──────────────────────────┘                     │   - default output device  │
                                                  └────────────────────────────┘
```

Why a separate process:
1. **Real-time audio can't tolerate GC pauses.** Chromium's V8 stalls
   for tens of ms; the audio callback needs to run every ~5 ms.
2. **Plugins crash.** A misbehaving VST that segfaults takes down its
   process, not the whole DAW.
3. **License isolation.** Plugin binaries load in the engine, not the UI.

## Message protocol

**Electron → engine** (one JSON object per line):

| cmd              | fields                                          |
|------------------|-------------------------------------------------|
| `list_plugins`   | —                                               |
| `load_plugin`    | `channelId`, `pluginId`                         |
| `unload_plugin`  | `channelId`                                     |
| `note_on`        | `channelId`, `pitch`, `velocity` (0..1)         |
| `note_off`       | `channelId`, `pitch`                            |
| `set_param`      | `channelId`, `paramIndex`, `value` (0..1)       |

**Engine → Electron** (one JSON object per line):

| event            | fields                                              |
|------------------|-----------------------------------------------------|
| `starting`       | —                                                   |
| `scanning`       | `name`, `index`, `total`                            |
| `ready`          | `plugins` (count)                                   |
| `plugin_list`    | `plugins` (array of {id, name, format, manufacturer, category, isInstrument}) |
| `plugin_loaded`  | `channelId`                                         |
| `error`          | `error`, `channelId?`                               |

## Next concrete steps

1. Implement the MIDI queue so `note_on` actually plays sound
2. Cache the plugin scan across launches (startup is ~10s on first run)
3. Route the sequencer transport to plugins
4. Show plugin UIs in native windows
5. Bundle the binary in the `.dmg` (already wired via `extraResources`)
6. Ship curated free plugins (Surge XT, Sfizz, Vitalium) alongside
