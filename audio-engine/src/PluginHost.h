#pragma once

// PluginHost — JUCE plugin scanning + instantiation + audio graph.
// Runs plugins through an AudioProcessorGraph fed by MIDI from the UI.

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_audio_utils/juce_audio_utils.h>
#include <functional>
#include <memory>
#include <mutex>

namespace nasty {

class PluginHost : private juce::AudioProcessorPlayer,
                   private juce::ChangeListener {
public:
    PluginHost();
    ~PluginHost() override;

    // ChangeListener — fires when the audio device changes (sleep/wake,
    // device unplug/plug). We re-initialize the device so audio doesn't stay
    // silent after macOS resumes the machine.
    void changeListenerCallback(juce::ChangeBroadcaster* source) override;

    using ScanProgress = std::function<void(const juce::String& name, int idx, int total)>;

    void scanDefaultPaths(const ScanProgress& onProgress = {});
    size_t pluginCount() const;

    // Load a cached plugin list from disk. Returns true if a cache existed
    // and was loaded — main() can then emit `ready` immediately without
    // waiting for a fresh scan.
    bool loadPluginCache(const juce::File& cacheFile);
    // Write the current plugin list to disk for the next boot.
    void savePluginCache(const juce::File& cacheFile) const;

    // Serialise the discovered plugin catalog as JSON-array-of-objects for the UI.
    juce::var pluginListAsJson() const;

    // Ensure audio output is open at the default device / rate.
    void startAudio();
    void stopAudio();

    // Load a plugin into a channel slot. Returns error string on failure, empty on success.
    // If base64State is non-empty, applies it via setStateInformation after
    // instantiation so plugins reload with their last-known state (Serato's
    // loaded sample, Serum patch, etc.).
    juce::String loadPlugin(const juce::String& channelId,
                            const juce::String& pluginId,
                            const juce::String& base64State = {});
    void unloadPlugin(const juce::String& channelId);

    // Create a General MIDI channel using the bundled FluidSynth + SoundFont.
    // Gives every user 128 built-in instruments (piano, strings, brass, drums,
    // etc.) with no plugin browsing. Returns error string on failure, empty
    // on success. gmProgram: 0-127 for melodic patches, 128 for drum kit.
    juce::String addGmChannel(const juce::String& channelId,
                              int gmProgram,
                              const juce::String& sf2Path);
    void setGmProgram(const juce::String& channelId, int gmProgram);

    // FL-style drum channel — loads a single WAV sample into a sample player.
    // Notes at rootNote play the sample at natural pitch; higher/lower notes
    // shift the playback rate. rootNote defaults to 60 (C5) if unspecified.
    juce::String addDrumChannel(const juce::String& channelId,
                                const juce::String& samplePath,
                                int rootNote);

    // Serialise every loaded plugin's state as { channelId: base64 }. Called
    // on song save so plugin state persists across app restarts.
    juce::var snapshotPluginStates();

    // Per-channel effect chain. Effects are VST/AU plugins inserted between
    // the channel's instrument and the master output, in slot order.
    // slotId is a stable per-slot identifier the front end owns (the same one
    // it uses to route double-click, drag-reorder, and state persistence).
    juce::String addEffect(const juce::String& channelId,
                           const juce::String& slotId,
                           const juce::String& pluginId,
                           const juce::String& base64State = {});
    void removeEffect(const juce::String& channelId, const juce::String& slotId);
    void reorderEffects(const juce::String& channelId, const juce::StringArray& newOrder);
    void bypassEffect(const juce::String& channelId, const juce::String& slotId, bool bypassed);
    void showEffectUI(const juce::String& channelId, const juce::String& slotId);
    void hideEffectUI(const juce::String& channelId, const juce::String& slotId);

    // Snapshot effect states as { channelId: { slotId: base64 } } so the save
    // file can restore not just which effects were loaded but their internal
    // state (Serato Effects delay time, Surge XT Effects preset, etc.).
    juce::var snapshotEffectStates();

    // Available audio devices + current selection, for the in-app picker.
    juce::var listAudioDevices();
    juce::String setOutputDevice(const juce::String& deviceName);

    // Create an audio-only "bus" — a mixer insert with no instrument, just an
    // input node + effect chain that other channels can route into. Effects
    // are added to it with the same addEffect() API using the bus's channelId.
    juce::String createBusChannel(const juce::String& channelId);

    // Route a channel's audio output to a target channel's input (which then
    // runs its own effect chain and feeds either master or another target).
    // Empty targetChannelId = route to master.
    void setChannelTarget(const juce::String& channelId, const juce::String& targetChannelId);

    // MIDI note events routed to a channel's plugin.
    void noteOn (const juce::String& channelId, int pitch, float velocity);
    void noteOff(const juce::String& channelId, int pitch);
    void allNotesOff(const juce::String& channelId);

    // Show / hide the plugin's native editor window. Safe to call from any
    // thread — dispatched to the JUCE message thread internally.
    void showPluginUI(const juce::String& channelId);
    void hidePluginUI(const juce::String& channelId);

    // Toggle whether open plugin windows float above other apps. Called when
    // Nasty (Electron) gains or loses focus so plugin windows don't sit on
    // top of Chrome/Slack when the user Cmd+Tabs away.
    void setPluginWindowsFloating(bool floating);

    // Hide (but keep alive) every open plugin window. Called when the user
    // clicks anywhere in Nasty so plugin windows behave like FL: click off,
    // they get out of the way. Re-shown by show_plugin_ui.
    void hideAllPluginUIs();

    // Parameter automation.
    void setParam(const juce::String& channelId, int paramIndex, float value01);

private:
    juce::AudioPluginFormatManager formatManager;
    juce::KnownPluginList          knownPlugins;
    juce::AudioDeviceManager       deviceManager;
    juce::AudioProcessorGraph      graph;

    struct EffectSlot {
        juce::String slotId;
        juce::AudioProcessorGraph::NodeID nodeId;
        bool bypassed = false;
    };

    struct ChannelSlot {
        juce::AudioProcessorGraph::NodeID pluginNodeId;
        juce::AudioProcessorGraph::NodeID injectorNodeId;
        int midiChannel = 1;
        std::vector<EffectSlot> effects; // FX chain in order: instrument → eff[0] → ... → out
        // Empty = route to master. Otherwise = route this channel's chain
        // output into the target channel's input (bus routing).
        juce::String targetChannelId;
        // True if this is a bus channel (no instrument, no MIDI). pluginNodeId
        // is a passthrough gain node that source channels connect audio into.
        bool isBus = false;
    };

    mutable std::mutex mutex;
    std::map<juce::String, ChannelSlot> channels; // by channelId
    bool audioRunning = false;

    // Rewire a channel's audio graph: instrument → active effects → master out.
    // Called after any effect chain mutation. Must be called under `mutex`.
    void rewireChannelUnlocked(ChannelSlot& slot);

    // Plugin editor windows are message-thread only — no lock needed.
    class PluginWindow;
    std::map<juce::String, std::unique_ptr<PluginWindow>> pluginWindows;
    // Effect editor windows keyed as "<channelId>::<slotId>".
    std::map<juce::String, std::unique_ptr<PluginWindow>> effectWindows;

    // Fixed-tempo play head shared by the graph so tempo-syncing plugins
    // (Serato slicers, arps, sync'd delays, LFOs) see valid host transport
    // info. Reports 120 BPM / 4-4 / stopped until we wire the real transport.
    std::unique_ptr<juce::AudioPlayHead> playHead;
};

} // namespace nasty
