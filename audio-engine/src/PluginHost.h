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

    // Tear down every channel + effect and return the graph to its empty
    // startup shape (master audio output + metronome intact; no channels,
    // no buses, no effect nodes). Called from the load-from-file path so
    // opening a song starts from a clean slate instead of double-adding on
    // top of the previous song's state. The JS side re-issues the normal
    // hydrate commands (create_bus, load_plugin, add_effect, ...) after.
    void resetGraph();

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
    // FLOW-owned wet/dry mix for the effect at (channelId, slotId). Value is
    // clamped to [0, 1]. Sets wetGain to `value` and dryGain to `1 - value`.
    // Plugin-agnostic — the plugin doesn't need to expose a mix param.
    void setEffectWetDry(const juce::String& channelId, const juce::String& slotId, float value);

    // Per-channel pan (-1 = full left, 0 = center, +1 = full right). Applied
    // by an equal-power channel-independent pan node downstream of the gain.
    void setChannelPan(const juce::String& channelId, float value);

    // Per-channel stereo width (0 = mono, 1 = full stereo). M/S processing
    // node downstream of the gain: side signal is scaled by width.
    void setChannelStereoWidth(const juce::String& channelId, float value);
    void showEffectUI(const juce::String& channelId, const juce::String& slotId);
    void hideEffectUI(const juce::String& channelId, const juce::String& slotId);

    // Snapshot effect states as { channelId: { slotId: base64 } } so the save
    // file can restore not just which effects were loaded but their internal
    // state (Serato Effects delay time, Surge XT Effects preset, etc.).
    juce::var snapshotEffectStates();

    // Available audio devices + current selection, for the in-app picker.
    juce::var listAudioDevices();
    juce::String setOutputDevice(const juce::String& deviceName);

    // Available INPUT devices (USB mics, interfaces). Kept separate from
    // listAudioDevices so the mixer's per-channel input picker never surfaces
    // an output-only device (built-in speakers, DisplayPort audio, etc.).
    juce::var listAudioInputs();

    // Bind the audio-input side of the device manager to this device. Empty
    // string closes the input side (mixer strips lose their signal but audio
    // playback continues). Reopens the device internally — brief interruption.
    // Bluetooth caveat: opening the input of a BT headset flips it to HFP
    // (24kHz mono) which wrecks music playback, so callers should pass a
    // wired USB mic / audio interface here, not the same device as output.
    juce::String setInputDevice(const juce::String& deviceName);

    juce::var currentInputSnapshot() const;

    // Create an audio-input channel: a passthrough that pulls signal from the
    // graph's audio input node into a mixer chain (effects + gain → target).
    // The channel exists even before an input device is bound — it just
    // carries silence until setInputDevice() connects a mic. Idempotent by id.
    juce::String createAudioInputChannel(const juce::String& channelId);

    // Flag any existing channel or bus to receive the graph audio input node's
    // signal. FL-style "IN" on a mixer insert: the bus already exists (created
    // by createBusChannel); this just wires the mic into it so the mic mixes
    // with anything else routed there. enabled=false removes the wiring.
    void setChannelAudioInput(const juce::String& channelId, bool enabled);

    // Start writing the current audio input to a WAV file under
    // ~/Music/Nasty Recordings/. Returns error string on failure (empty on
    // success). outPath is set to the file path on success. Idempotent — a
    // second call while recording is a no-op returning "already recording".
    juce::String startRecording(juce::String& outPath);

    // Stop the active recording, flush + close the file. outPath and
    // outSamples are set to the file path and total captured sample count.
    // Empty error on success; "not recording" if nothing was active.
    juce::String stopRecording(juce::String& outPath, juce::int64& outSamples);

    // Add a WAV clip that plays back during SONG-mode transport. clipId is
    // UI-owned (used later by removeAudioClip / setAudioClipPosition).
    // path must exist. busId names the mixer bus to route into. All times in
    // session samples. Returns error string on failure, empty on success.
    juce::String addAudioClip(const juce::String& clipId,
                              const juce::String& path,
                              const juce::String& busId,
                              juce::int64 songStartSample,
                              juce::int64 lengthSamples);
    void removeAudioClip(const juce::String& clipId);
    void setAudioClipPosition(const juce::String& clipId,
                              juce::int64 songStartSample,
                              juce::int64 lengthSamples);

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

    // Add / replace a signal send on this channel. Sends tap the channel's
    // gain output and deliver it to a specific input port on the target — for
    // now "main" (mix into target audio) or "sidechain" (feed the target
    // bus's first sidechain-capable plugin's detector input). Empty
    // targetChannelId removes any existing send with this sendId.
    juce::String setChannelSend(const juce::String& channelId,
                                const juce::String& sendId,
                                const juce::String& targetChannelId,
                                const juce::String& targetInput);
    void removeChannelSend(const juce::String& channelId,
                           const juce::String& sendId);

    // MIDI note events routed to a channel's plugin.
    void noteOn (const juce::String& channelId, int pitch, float velocity);
    void noteOff(const juce::String& channelId, int pitch);
    void allNotesOff(const juce::String& channelId);

    // Non-note MIDI events routed to a channel's plugin. Used for driving
    // in-plugin state that the standard VST/AU parameter API doesn't expose
    // (FL Studio AU's FLEX preset browser is the flagship case). The MIDI
    // channel defaults to the channel slot's assigned channel but can be
    // overridden — some hosted plugins listen on a specific MIDI channel
    // internally (FL Studio AU routes MIDI channel N to its internal
    // channel N).
    void sendProgramChange(const juce::String& channelId, int program, int midiChannel);
    void sendControlChange(const juce::String& channelId, int controller, int value, int midiChannel);

    // Per-channel volume, applied by scaling outgoing noteOn velocities. Cheap
    // enough to change every buffer if the user drags a slider. Not a true
    // audio-level gain, but works uniformly across every velocity-honouring
    // instrument (all synths + drum samplers).
    void setChannelGain(const juce::String& channelId, float gain01);

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
        juce::AudioProcessorGraph::NodeID nodeId;         // plugin node
        // FLOW-owned wet/dry wrap. Two gain nodes in the graph form a parallel
        // topology: prev → plugin → wetGain and prev → dryGain, both feeding
        // the next stage's input where JUCE auto-sums them. Linear mix:
        // wetGain.gain = wetDry, dryGain.gain = 1 - wetDry. Plugin-agnostic,
        // works even when the plugin exposes no mix param.
        juce::AudioProcessorGraph::NodeID wetGainNodeId;
        juce::AudioProcessorGraph::NodeID dryGainNodeId;
        bool bypassed = false;
        float wetDry = 1.0f;  // 0 = fully dry (bypass-like), 1 = fully wet
    };

    // One outgoing signal send. Stored on the source ChannelSlot. General
    // enough to cover sidechain today AND aux sends / wet-dry routing later
    // — the data shape is the 100-year commitment; only the wiring logic
    // varies per targetInput type.
    struct SendSlot {
        juce::String sendId;          // stable id owned by the UI
        juce::String targetChannelId; // destination bus id
        juce::String targetInput;     // "main" (channels 0,1) or "sidechain" (2,3)
    };

    struct ChannelSlot {
        juce::AudioProcessorGraph::NodeID pluginNodeId;
        juce::AudioProcessorGraph::NodeID injectorNodeId;
        // Per-channel audio gain node — sits at the tail of the chain, right
        // before the signal enters the target bus / master. Written to by
        // setChannelGain. Empty node ID means "no gain stage" (legacy shape,
        // shouldn't happen for channels created after this field was added).
        juce::AudioProcessorGraph::NodeID gainNodeId;
        int midiChannel = 1;
        std::vector<EffectSlot> effects; // FX chain in order: instrument → eff[0] → ... → out
        // Empty = route to master. Otherwise = route this channel's chain
        // output into the target channel's input (bus routing).
        juce::String targetChannelId;
        // True if this is a bus channel (no instrument, no MIDI). pluginNodeId
        // is a passthrough gain node that source channels connect audio into.
        bool isBus = false;
        // True if this channel sources audio from the graph's audio input node
        // (i.e. a microphone / line-in channel). pluginNodeId is a passthrough
        // fed by audioInputNode → passthrough connections that live outside
        // the normal rewire tear-down. Combined with isBus=false, isAudioInput=true
        // signals rewire to leave its input-side connections alone.
        bool isAudioInput = false;
        // Additional sends beyond the primary targetChannelId route. Each one
        // taps this channel's gain output and delivers it to a specific input
        // port on the target — main (mix in) or sidechain (feed a compressor's
        // detector). Empty = no extra sends, only the primary route runs.
        std::vector<SendSlot> sends;
        // Stereo-width (M/S) and pan (equal-power) nodes, chained after
        // gainNode. Empty NodeID = legacy slot that doesn't have them; the
        // rewire pass gracefully skips missing nodes. Order in the graph:
        //   gain → width → pan → target
        juce::AudioProcessorGraph::NodeID widthNodeId;
        juce::AudioProcessorGraph::NodeID panNodeId;
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

    // Re-rewire every channel that has a send targeting `targetChannelId`.
    // Called whenever the target bus's effect chain changes so a deferred
    // sidechain send picks up a freshly-loaded compressor. Must be under mutex.
    void rewireSendSourcesToUnlocked(const juce::String& targetChannelId);

    // Factory: add a MidiInjector to the graph with its transport wired up.
    // Every code path that creates a channel (loadPlugin, addGmChannel,
    // addDrumChannel) goes through here so pattern playback works uniformly.
    juce::AudioProcessorGraph::Node::Ptr addInjectorNode();
    juce::AudioProcessorGraph::Node::Ptr addGainNode();
    juce::AudioProcessorGraph::Node::Ptr addPanNode();
    juce::AudioProcessorGraph::Node::Ptr addWidthNode();

    // (Re)establish connections from the graph's audio input node into every
    // audio-input channel's passthrough. Called after setInputDevice() so the
    // input-side wiring picks up the new device's channel count. Safe to call
    // when no input device is bound — will just do nothing.
    void reconnectAudioInputsUnlocked();

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

    // Audio-input recording. writer holds a WAV writer created when the user
    // hits Record; the audio callback writes each buffer of input samples to
    // it directly (writeFromFloatArrays blocks briefly on disk — fine for one
    // mic at 48kHz/24-bit; refactor to ThreadedWriter if we start dropping).
    std::atomic<bool> recordingActive{false};
    std::unique_ptr<juce::AudioFormatWriter> recordingWriter;
    juce::File recordingFile;
    std::atomic<juce::int64> recordingSamples{0};

    // Loaded audio clips playing back during SONG-mode transport. Each one
    // is an AudioClipPlayer node in the graph, wired to its bus's input.
    struct AudioClipSlot {
        juce::AudioProcessorGraph::NodeID nodeId;
        juce::String busId;
    };
    std::map<juce::String, AudioClipSlot> audioClips;
    juce::AudioFormatManager clipFormatManager;

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
