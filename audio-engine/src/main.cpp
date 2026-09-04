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

int main(int /*argc*/, char** /*argv*/) {
    juce::ScopedJuceInitialiser_GUI juceInit;

    // Unbuffered stdout so Electron sees lines immediately.
    std::setvbuf(stdout, nullptr, _IOLBF, 0);

    nasty::PluginHost host;
    nasty::StdioBridge bridge(host);

    // Send ready event before scanning (scan can take seconds).
    bridge.sendEvent({{"event", juce::var("starting")}});

    host.scanDefaultPaths([&](const juce::String& name, int idx, int total) {
        bridge.sendEvent({
            {"event", juce::var("scanning")},
            {"name",  juce::var(name)},
            {"index", juce::var(idx)},
            {"total", juce::var(total)},
        });
    });

    bridge.sendEvent({
        {"event",   juce::var("ready")},
        {"plugins", juce::var((int)host.pluginCount())},
    });

    // Block on JUCE's message loop for plugin UIs, timers, etc.
    // The bridge reads stdin on a background thread and dispatches to us.
    bridge.startReadThread();
    juce::MessageManager::getInstance()->runDispatchLoop();
    return 0;
}
