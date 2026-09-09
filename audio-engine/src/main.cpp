// Nasty Audio Engine — entry point.
//
// This binary runs as a subprocess of the Electron app. It hosts native
// audio plugins (VST3/AU) and speaks JSON lines over stdin/stdout to the UI.
//
// Wire format: one JSON object per line, both directions.
//   UI → engine: {"cmd":"scan_plugins"}          {"cmd":"load_plugin","channelId":"...","pluginId":"..."}
//   engine → UI: {"event":"ready","plugins":N}   {"event":"plugin_list","plugins":[...]}

#include <juce_audio_utils/juce_audio_utils.h>
#include <juce_audio_processors/juce_audio_processors.h>

#include "PluginHost.h"
#include "StdioBridge.h"

#include <iostream>
#include <thread>

#if __APPLE__
namespace nasty { void setSubprocessAsAgentApp(); }
#endif

int main(int /*argc*/, char** /*argv*/) {
    juce::ScopedJuceInitialiser_GUI juceInit;

#if __APPLE__
    // Behave as a background helper: can own windows, never steals focus.
    nasty::setSubprocessAsAgentApp();
#endif

    // Unbuffered stdout so Electron sees lines immediately.
    std::setvbuf(stdout, nullptr, _IOLBF, 0);

    nasty::PluginHost host;
    nasty::StdioBridge bridge(host);

    // Send ready event before scanning (scan can take seconds).
    bridge.sendEvent({{"event", juce::var("starting")}});

    // Skip the plugin scan when NASTY_SKIP_SCAN=1. Useful for engine unit
    // tests (transport, MIDI routing) that don't need plugins loaded, and
    // for quickly reproducing bugs without the ~30s VST3/AU discovery pass.
    const char* skipScanEnv = std::getenv("NASTY_SKIP_SCAN");
    const bool skipScan = skipScanEnv && skipScanEnv[0] == '1';
    if (!skipScan) {
        host.scanDefaultPaths([&](const juce::String& name, int idx, int total) {
            bridge.sendEvent({
                {"event", juce::var("scanning")},
                {"name",  juce::var(name)},
                {"index", juce::var(idx)},
                {"total", juce::var(total)},
            });
        });
    }

    bridge.sendEvent({
        {"event",   juce::var("ready")},
        {"plugins", juce::var((int)host.pluginCount())},
    });

    // Open the audio device up-front so the Transport starts advancing.
    // The audio callback is the ONLY thing that advances the sample counter,
    // so gating the transport on "first plugin loaded" would leave the UI
    // playhead frozen until then. Idempotent — subsequent plugin loads reuse
    // the running device.
    host.startAudio();

    // Block on JUCE's message loop for plugin UIs, timers, etc.
    // The bridge reads stdin on a background thread and dispatches to us.
    bridge.startReadThread();
    // Emit transport_position at 60 Hz so the UI can drive its playhead off
    // the engine clock. Cheap; only emits while the transport is playing
    // (plus one settling tick on stop).
    bridge.startPositionBroadcaster(60);
    juce::MessageManager::getInstance()->runDispatchLoop();
    return 0;
}
