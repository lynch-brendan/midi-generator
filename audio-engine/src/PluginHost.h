#pragma once

// PluginHost — JUCE plugin scanning + instantiation + audio graph.
// Runs plugins through an AudioProcessorGraph fed by MIDI from the UI.

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_audio_utils/juce_audio_utils.h>
#include <functional>
#include <memory>
#include <mutex>

namespace nasty {

class PluginHost : private juce::AudioProcessorPlayer {
public:
    PluginHost();
    ~PluginHost() override;

    using ScanProgress = std::function<void(const juce::String& name, int idx, int total)>;

    void scanDefaultPaths(const ScanProgress& onProgress = {});
    size_t pluginCount() const;

    // Serialise the discovered plugin catalog as JSON-array-of-objects for the UI.
    juce::var pluginListAsJson() const;

    // Ensure audio output is open at the default device / rate.
    void startAudio();
    void stopAudio();

    // Load a plugin into a channel slot. Returns error string on failure, empty on success.
    juce::String loadPlugin(const juce::String& channelId, const juce::String& pluginId);
    void unloadPlugin(const juce::String& channelId);

    // MIDI note events routed to a channel's plugin.
    void noteOn (const juce::String& channelId, int pitch, float velocity);
    void noteOff(const juce::String& channelId, int pitch);
    void allNotesOff(const juce::String& channelId);

    // Show / hide the plugin's native editor window. Safe to call from any
    // thread — dispatched to the JUCE message thread internally.
    void showPluginUI(const juce::String& channelId);
    void hidePluginUI(const juce::String& channelId);

    // Parameter automation.
    void setParam(const juce::String& channelId, int paramIndex, float value01);

private:
    juce::AudioPluginFormatManager formatManager;
    juce::KnownPluginList          knownPlugins;
    juce::AudioDeviceManager       deviceManager;
    juce::AudioProcessorGraph      graph;

    struct ChannelSlot {
        juce::AudioProcessorGraph::NodeID pluginNodeId;
        juce::AudioProcessorGraph::NodeID injectorNodeId;
        int midiChannel = 1;
    };

    mutable std::mutex mutex;
    std::map<juce::String, ChannelSlot> channels; // by channelId
    bool audioRunning = false;

    // Plugin editor windows are message-thread only — no lock needed.
    class PluginWindow;
    std::map<juce::String, std::unique_ptr<PluginWindow>> pluginWindows;
};

} // namespace nasty
