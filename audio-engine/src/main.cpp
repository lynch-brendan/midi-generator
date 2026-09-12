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

    // Cache files (JSON + XML). Same dir the plugin-scan dead-mans list uses.
    auto supportDir = juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory)
        .getChildFile("nasty");
    supportDir.createDirectory();
    auto pluginCacheFile = supportDir.getChildFile("plugin-cache.xml");
    auto presetCacheFile = supportDir.getChildFile("plugin-presets.json");

    if (!skipScan) {
        // Hydrate the discovered-plugins list from disk BEFORE the fresh scan.
        // Without this, every boot re-walks every VST3/AU on the system, which
        // pulls each plugin's static init code — for Qt-based plugins like
        // Serato Sample that means their splash/scenegraph pops for a beat.
        // With the cache loaded, PluginDirectoryScanner short-circuits any
        // file that hasn't changed since last scan.
        host.loadPluginCache(pluginCacheFile);
        host.scanDefaultPaths([&](const juce::String& name, int idx, int total) {
            bridge.sendEvent({
                {"event", juce::var("scanning")},
                {"name",  juce::var(name)},
                {"index", juce::var(idx)},
                {"total", juce::var(total)},
            });
        });
        host.savePluginCache(pluginCacheFile);

        // Load the preset (program) cache from disk BEFORE the fresh scan so
        // pluginsAlreadyKnown short-circuits. First launch does the full
        // instantiation pass (~30-90s for a large plugin library); every
        // launch after that is instant because cache keys stay valid.
        host.loadPresetCache(presetCacheFile);
        host.scanAllPluginPresets([&](const juce::String& name, int idx, int total) {
            bridge.sendEvent({
                {"event", juce::var("scanning_presets")},
                {"name",  juce::var(name)},
                {"index", juce::var(idx)},
                {"total", juce::var(total)},
            });
        });
        host.savePresetCache(presetCacheFile);
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

    // Tell the UI the output device is actually hooked up. `ready` above only
    // means "plugin scan done"; hitting play before this would silently miss
    // notes. The UI holds a loading overlay until this event fires.
    {
        auto snap = host.currentOutputSnapshot();
        auto* obj = snap.getDynamicObject();
        juce::String devName = obj ? obj->getProperty("deviceName").toString() : juce::String();
        double sr           = obj ? (double) obj->getProperty("sampleRate")   : 0.0;
        int outCh           = obj ? (int)    obj->getProperty("outputChannels") : 0;
        bridge.sendEvent({
            {"event",          juce::var("audio_ready")},
            {"deviceName",     juce::var(devName)},
            {"sampleRate",     juce::var(sr)},
            {"outputChannels", juce::var(outCh)},
        });
    }

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
