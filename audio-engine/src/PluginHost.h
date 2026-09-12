#pragma once

// PluginHost — JUCE plugin scanning + instantiation + audio graph.
// Runs plugins through an AudioProcessorGraph fed by MIDI from the UI.

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_audio_utils/juce_audio_utils.h>
#include <functional>
#include <memory>
#include <mutex>

#include "Transport.h"
#include "PatternPlayer.h"
#include "Metronome.h"

namespace nasty {

class PluginHost : private juce::AudioProcessorPlayer,
                   private juce::ChangeListener {
public:
    PluginHost();
    ~PluginHost() override;

    // The engine's single time source. Public read/write API on the Transport
    // itself is thread-safe (atomic).
    Transport& getTransport() noexcept { return transport; }
    PatternPlayer& getPatternPlayer() noexcept { return patternPlayer; }

    // Enable / disable the engine-hosted metronome. Sample-accurate against
    // the Transport — clicks land on beat boundaries in the same audio
    // callback that fires pattern notes. Cannot drift.
    void setMetronomeEnabled(bool v);

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

    // Read each installed plugin's factory-preset list. Instantiates every
    // plugin briefly to query `getNumPrograms()` + `getProgramName()`. Any
    // pluginId already present in `presetsByPluginId` is skipped, so this is
    // cheap after the first call once the disk cache is populated. The AI
    // uses this manifest to pick "Wobble Bass" style patches by name.
    void scanAllPluginPresets(const ScanProgress& onProgress = {});
    bool loadPresetCache(const juce::File& cacheFile);
    void savePresetCache(const juce::File& cacheFile) const;

    // Serialise the discovered plugin catalog as JSON-array-of-objects for the UI.
    juce::var pluginListAsJson() const;

    // Ensure audio output is open at the default device / rate.
    void startAudio();
    void stopAudio();

    // Load a plugin into a channel slot. Returns error string on failure, empty on success.
    // If base64State is non-empty, applies it via setStateInformation after
    // instantiation so plugins reload with their last-known state (Serato's
    // loaded sample, Serum patch, etc.).
    // If presetName is non-empty, does a case-insensitive fuzzy match against
    // the plugin's program list and calls setCurrentProgram. Silent no-op if
    // the plugin has no matching program.
    juce::String loadPlugin(const juce::String& channelId,
                            const juce::String& pluginId,
                            const juce::String& base64State = {},
                            const juce::String& presetName = {});
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
                           const juce::String& base64State = {},
                           const juce::String& presetName = {});
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

    // Snapshot of the currently-open output device — name, sample rate, output
    // channel count. Empty name / rate 0 means no device came up. Used by the
    // UI's boot loading overlay to gate playback until output is live.
    juce::var currentOutputSnapshot() const;

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

    // Fire allNotesOff on every registered channel. Used by transport stop
    // so notes held mid-pattern don't get stuck when playback halts before
    // their noteOff was injected.
    void panicAllChannels();

    // Per-channel pattern edits. Notes replay every loop iteration; atSample
    // is relative to the loop origin. Idempotent by noteId — setting the
    // same noteId replaces the existing entry. Audio-thread safe: writes
    // use a SpinLock that the audio-thread walker tryLocks (skipping the
    // buffer on contention, which for UI-edit rates is negligible).
    void setPatternNote(const juce::String& channelId,
                        const juce::String& noteId,
                        int pitch, float velocity,
                        std::int64_t atSample,
                        std::int64_t durationSamples);
    void clearPatternNote(const juce::String& channelId,
                          const juce::String& noteId);
    void clearPattern(const juce::String& channelId);

    // SONG-mode pattern edits. Same shape as setPatternNote/clearPatternNote,
    // but keyed by patternId so a channel can hold many patterns at once and
    // the arrangement references them by ID. Notes edited here don't affect
    // PAT-mode playback (which reads the flat patternNotes map instead).
    void setPatternNoteIn(const juce::String& channelId,
                          const juce::String& patternId,
                          const juce::String& noteId,
                          int pitch, float velocity,
                          std::int64_t atSample,
                          std::int64_t durationSamples);
    void clearPatternNoteIn(const juce::String& channelId,
                            const juce::String& patternId,
                            const juce::String& noteId);
    void clearPatternInChannel(const juce::String& channelId,
                               const juce::String& patternId);
    void clearAllPatternsIn(const juce::String& channelId);

    // Per-channel arrangement lane. `clips` is a juce::var array of objects
    // shaped { patternId, songStartSample, lengthSamples, patternLoopLenSamples }.
    // Replaces the channel's arrangement wholesale (atomic swap under the
    // injector's SpinLock — the audio thread picks up the new arrangement on
    // its very next buffer, no cross-buffer bleed).
    void setChannelArrangement(const juce::String& channelId,
                               const juce::var& clips);
    void clearChannelArrangement(const juce::String& channelId);

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

    // Parameter automation. `slotId` empty targets the channel's instrument;
    // non-empty targets the effect chain slot with that id (as returned from
    // addEffect). Silent no-op if either the channel, slot, or index is out
    // of range — Claude's job to send a valid index, not the engine's to
    // apologise.
    void setParam(const juce::String& channelId,
                  const juce::String& slotId,
                  int paramIndex, float value01);

    // Enumerate the parameters of the plugin at `channelId::slotId` as a
    // JSON-array of {index, name, value}. slotId empty = channel's instrument;
    // non-empty = effect slot. Empty array if nothing's loaded there. This
    // is what the AI reads to know what knobs it can turn.
    juce::var paramsForOwner(const juce::String& channelId,
                             const juce::String& slotId = {}) const;

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

    // Preset (program) names per plugin, filled by scanAllPluginPresets and
    // persisted via loadPresetCache/savePresetCache. Empty StringArray means
    // "we've checked; this plugin has no exposed programs" — different from
    // "not scanned yet." A missing key means "not scanned yet."
    std::map<juce::String, juce::StringArray> presetsByPluginId;

    // Rewire a channel's audio graph: instrument → active effects → master out.
    // Called after any effect chain mutation. Must be called under `mutex`.
    void rewireChannelUnlocked(ChannelSlot& slot);

    // Factory: add a MidiInjector to the graph with its transport wired up.
    // Every code path that creates a channel (loadPlugin, addGmChannel,
    // addDrumChannel) goes through here so pattern playback works uniformly.
    juce::AudioProcessorGraph::Node::Ptr addInjectorNode();

    // Plugin editor windows are message-thread only — no lock needed.
    class PluginWindow;
    std::map<juce::String, std::unique_ptr<PluginWindow>> pluginWindows;
    // Effect editor windows keyed as "<channelId>::<slotId>".
    std::map<juce::String, std::unique_ptr<PluginWindow>> effectWindows;

    // Play head shared by the graph so tempo-syncing plugins (arps, sync'd
    // delays, LFOs, slicers) see valid host transport info. Reads live values
    // straight off the Transport.
    std::unique_ptr<juce::AudioPlayHead> playHead;

    // Single source of truth for time. Advanced by the audio callback below.
    Transport transport;

    // Per-pattern loop state. Owns its own position counter that advances +
    // wraps in the audio callback; the walker + visual playhead read from
    // this so loop-length changes don't teleport the playhead.
    PatternPlayer patternPlayer;

    // Engine-hosted metronome. Added to the graph as a node routed straight
    // to the master output. Enabled/disabled via setMetronomeEnabled().
    juce::AudioProcessorGraph::Node::Ptr metronomeNode;

    // AudioIODeviceCallback overrides — wrap the AudioProcessorPlayer base so
    // we can advance the Transport around each buffer, and publish the real
    // device sample rate to the Transport when the device opens.
    void audioDeviceIOCallbackWithContext(const float* const* inputChannelData,
                                          int numInputChannels,
                                          float* const* outputChannelData,
                                          int numOutputChannels,
                                          int numSamples,
                                          const juce::AudioIODeviceCallbackContext& context) override;
    void audioDeviceAboutToStart(juce::AudioIODevice* device) override;
    void audioDeviceStopped() override;
};

} // namespace nasty
