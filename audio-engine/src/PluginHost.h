#pragma once

// PluginHost — thin wrapper around JUCE's AudioPluginFormatManager +
// KnownPluginList. Handles scanning, instantiation, and eventual routing.
//
// Status: SCAFFOLDING. Real implementation pending.

#include <juce_audio_processors/juce_audio_processors.h>
#include <memory>
#include <vector>

namespace nasty {

class PluginHost {
public:
    PluginHost();
    ~PluginHost();

    // Enumerate plugins from OS default locations (~/Library/Audio/Plug-Ins on macOS,
    // %COMMONPROGRAMFILES%/VST3 on Windows, etc). Blocks — call once at startup.
    void scanDefaultPaths();

    // How many plugins we know about after scan.
    size_t pluginCount() const;

    // JSON-serialisable list for the UI: [{id, name, format, manufacturer, category}, ...]
    juce::var pluginListAsJson() const;

    // Instantiate a plugin by KnownPluginList unique id. Returns nullptr on failure.
    std::unique_ptr<juce::AudioPluginInstance> instantiate(const juce::String& pluginId,
                                                            double sampleRate,
                                                            int blockSize,
                                                            juce::String& outError);

private:
    juce::AudioPluginFormatManager formatManager;
    juce::KnownPluginList          knownPlugins;
};

} // namespace nasty
