#include "PluginHost.h"
#include "GmSynth.h"
#include "SampleDrum.h"
#include "AudioClipPlayer.h"
#include "NastyDucker.h"
#include <iostream>
#include <cstdio>

#if __APPLE__
namespace nasty {
    void makeWindowNonActivating(void* nativeViewHandle);
    void setWindowFloating(void* nativeViewHandle, bool floating);
    bool isEngineAppActive();
}
#endif

namespace nasty {

using Graph = juce::AudioProcessorGraph;

// A note in a per-channel pattern. atSample is relative to the loop origin,
// so playback of the same pattern in every loop iteration just adds the
// iteration's base offset. All fields UI-owned.
struct PatternNote {
    int          pitch;              // MIDI note 0-127
    float        velocity;           // 0.0-1.0
    std::int64_t atSample;           // position within [0, loopLengthSamples)
    std::int64_t durationSamples;    // note length; noteOff = atSample + this
};

// SONG mode: one placement of a pattern on a channel's arrangement lane.
// The pattern plays ONCE starting at songStartSample. If lengthSamples >
// patternLoopLenSamples, the tail is silence (FL behavior). If it's shorter,
// the pattern is truncated at the clip's end.
struct ArrangementClip {
    std::int64_t songStartSample;         // absolute Transport sample
    std::int64_t lengthSamples;           // how far the clip extends in song time
    std::int64_t patternLoopLenSamples;   // the pattern's own bar-boundary length
    juce::String patternId;               // key into notesByPattern
};

// MIDI-only processor sitting in front of each plugin. Serves two producers:
//   1. UI-triggered notes (preview/keyboard/held) via MidiMessageCollector.
//      Lock-free by construction — that's the collector's whole job.
//   2. Pattern playback — the audio callback walks a per-channel note list
//      and injects noteOn/noteOff at exact sample offsets inside the buffer.
//      Pattern edits are UI-thread; audio thread uses SpinLock::tryEnter so
//      it never blocks. Missing one buffer's pattern injection is inaudible.
namespace {
class MidiInjector : public juce::AudioProcessor {
public:
    juce::MidiMessageCollector collector;

    // Non-owning pointers to the engine's clock + pattern-loop state. Read on
    // the audio thread to decide which sample offsets the pattern maps to.
    const Transport*      transport      = nullptr;
    const PatternPlayer*  patternPlayer  = nullptr;

    // MIDI channel used for pattern-injected notes (1..16). Matches the
    // channel used for UI-triggered noteOn calls.
    int patternMidiChannel = 1;

    // Per-channel gain applied by scaling outgoing noteOn velocities. Not a
    // true audio-level gain (that'd need a dedicated gain node in the graph),
    // but works for every velocity-honouring instrument — which is all synths
    // and drum samplers. Written from the UI thread, read from the audio
    // thread every buffer. Default 1.0 = pass-through.
    std::atomic<float> gain{1.0f};

    // Helper: clamp + scale a MIDI velocity (0..127 float) by gain.
    float scaleVel(float v) const noexcept {
        const float g = gain.load(std::memory_order_relaxed);
        const float out = v * g;
        return out < 0.0f ? 0.0f : (out > 127.0f ? 127.0f : out);
    }

    // Pattern data. UI thread writes under fullLock; audio thread reads under
    // tryLock and skips this buffer if it can't get in.
    //
    // Two coexisting shapes, one lock:
    //   * patternNotes           — PAT mode. Flat map of the currently-loaded
    //                              pattern's notes. Walker fires these looped
    //                              at the PatternPlayer position.
    //   * notesByPattern         — SONG mode. Keyed by patternId so multiple
    //                              patterns can live in the injector at once
    //                              and clips can reference them by ID.
    //   * arrangement            — SONG mode. Ordered clips on this channel's
    //                              lane; the walker plays each clip's pattern
    //                              once at clip start, silence after pattern
    //                              end (matches FL).
    juce::SpinLock patternLock;
    std::map<juce::String, PatternNote> patternNotes;
    std::map<juce::String, std::map<juce::String, PatternNote>> notesByPattern;
    std::vector<ArrangementClip> arrangement;

    // UI-facing PAT-mode pattern editing API. Idempotent by noteId — replacing
    // a noteId's entry updates it in place.
    void uiSetNote(const juce::String& noteId, const PatternNote& note) {
        const juce::SpinLock::ScopedLockType lock(patternLock);
        patternNotes[noteId] = note;
    }
    void uiClearNote(const juce::String& noteId) {
        const juce::SpinLock::ScopedLockType lock(patternLock);
        patternNotes.erase(noteId);
    }
    void uiClearAll() {
        const juce::SpinLock::ScopedLockType lock(patternLock);
        patternNotes.clear();
    }

    // UI-facing SONG-mode editors. Same lock; edits picked up by the walker
    // on the very next buffer.
    void uiSetNoteInPattern(const juce::String& patternId,
                            const juce::String& noteId,
                            const PatternNote& note) {
        const juce::SpinLock::ScopedLockType lock(patternLock);
        notesByPattern[patternId][noteId] = note;
    }
    void uiClearNoteInPattern(const juce::String& patternId,
                              const juce::String& noteId) {
        const juce::SpinLock::ScopedLockType lock(patternLock);
        auto it = notesByPattern.find(patternId);
        if (it != notesByPattern.end()) it->second.erase(noteId);
    }
    void uiClearPatternInChannel(const juce::String& patternId) {
        const juce::SpinLock::ScopedLockType lock(patternLock);
        notesByPattern.erase(patternId);
    }
    void uiClearAllPatterns() {
        const juce::SpinLock::ScopedLockType lock(patternLock);
        notesByPattern.clear();
    }
    void uiSetArrangement(std::vector<ArrangementClip> clips) {
        const juce::SpinLock::ScopedLockType lock(patternLock);
        arrangement = std::move(clips);
    }
    void uiClearArrangement() {
        const juce::SpinLock::ScopedLockType lock(patternLock);
        arrangement.clear();
    }

    MidiInjector() : juce::AudioProcessor(BusesProperties()) {}

    const juce::String getName() const override    { return "MidiInjector"; }
    void prepareToPlay(double sr, int) override    { collector.reset(sr); }
    void releaseResources() override               {}
    bool acceptsMidi() const override              { return true; }
    bool producesMidi() const override             { return true; }
    bool isMidiEffect() const override             { return true; }
    double getTailLengthSeconds() const override   { return 0.0; }

    void processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer& midi) override {
        const int numSamples = buf.getNumSamples();
        collector.removeNextBlockOfMessages(midi, numSamples);
        injectPattern(midi, numSamples);
    }
    void processBlock(juce::AudioBuffer<double>& buf, juce::MidiBuffer& midi) override {
        const int numSamples = buf.getNumSamples();
        collector.removeNextBlockOfMessages(midi, numSamples);
        injectPattern(midi, numSamples);
    }
    using AudioProcessor::processBlock;

    juce::AudioProcessorEditor* createEditor() override    { return nullptr; }
    bool hasEditor() const override                        { return false; }
    int getNumPrograms() override                          { return 1; }
    int getCurrentProgram() override                       { return 0; }
    void setCurrentProgram(int) override                   {}
    const juce::String getProgramName(int) override        { return {}; }
    void changeProgramName(int, const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override  {}
    void setStateInformation(const void*, int) override    {}

private:
    // Dispatch based on Transport mode. PAT walks the looping PatternPlayer;
    // SONG walks the monotonic Transport clock against the arrangement.
    void injectPattern(juce::MidiBuffer& midi, int numSamples) {
        if (transport == nullptr) return;
        if (transport->getMode() == Transport::Mode::SONG)
            injectSongMode(midi, numSamples);
        else
            injectPatMode(midi, numSamples);
    }

    // PAT mode. Walk the pattern and inject any noteOn/noteOff falling in this
    // buffer. Called on the audio thread, real-time safe.
    //
    // Position comes from PatternPlayer — a state-based counter that
    // advances + wraps in its own beginBuffer/endBuffer. So the walker just
    // needs to answer "which notes are in [bufPos, bufPos + numSamples)?",
    // with a small extra check for buffers that span the wrap boundary
    // (rare — only when a buffer straddles the loop end).
    void injectPatMode(juce::MidiBuffer& midi, int numSamples) {
        if (patternPlayer == nullptr) return;
        if (!transport->getIsPlaying()) return;
        // During count-in the Transport rides at negative samples but the
        // PatternPlayer stays parked at 0. Without this guard the walker
        // would re-fire whatever's at pattern position 0 on every audio
        // buffer of the count-in → the rapid-fire high-pitched noise.
        if (transport->getBufferStartSample() < 0) return;
        const std::int64_t loopLen = patternPlayer->getLoopLengthSamples();
        if (loopLen <= 0) return;

        const std::int64_t bufPos = patternPlayer->getBufferStartPosition();
        const std::int64_t bufEnd = bufPos + numSamples;

        const juce::SpinLock::ScopedTryLockType tryLock(patternLock);
        if (!tryLock.isLocked()) return;

        // Fire notes that land in [bufPos, min(bufEnd, loopLen)) at their
        // natural offset within the buffer.
        const std::int64_t firstSegEnd = juce::jmin(bufEnd, loopLen);
        for (const auto& [_, note] : patternNotes) {
            if (note.atSample >= loopLen) continue; // past pattern content
            const std::int64_t onPos  = note.atSample;
            const std::int64_t offPos = note.atSample + note.durationSamples;
            if (onPos >= bufPos && onPos < firstSegEnd) {
                midi.addEvent(juce::MidiMessage::noteOn(
                    patternMidiChannel, note.pitch, scaleVel(note.velocity)),
                    (int) (onPos - bufPos));
            }
            if (offPos >= bufPos && offPos < firstSegEnd) {
                midi.addEvent(juce::MidiMessage::noteOff(
                    patternMidiChannel, note.pitch),
                    (int) (offPos - bufPos));
            }
        }

        // Buffer straddles the wrap: fire notes that land in [0, bufEnd - loopLen)
        // at offsets shifted by the "distance to wrap" so they sit at the
        // correct sample within this buffer.
        if (bufEnd > loopLen) {
            const std::int64_t wrappedEnd = bufEnd - loopLen;
            const std::int64_t offsetAfterWrap = loopLen - bufPos;
            for (const auto& [_, note] : patternNotes) {
                if (note.atSample >= loopLen) continue;
                const std::int64_t onPos  = note.atSample;
                const std::int64_t offPos = note.atSample + note.durationSamples;
                if (onPos >= 0 && onPos < wrappedEnd) {
                    midi.addEvent(juce::MidiMessage::noteOn(
                        patternMidiChannel, note.pitch, scaleVel(note.velocity)),
                        (int) (onPos + offsetAfterWrap));
                }
                if (offPos >= 0 && offPos < wrappedEnd) {
                    midi.addEvent(juce::MidiMessage::noteOff(
                        patternMidiChannel, note.pitch),
                        (int) (offPos + offsetAfterWrap));
                }
            }
        }
    }

    // SONG mode. Walk this channel's arrangement and inject any noteOn/noteOff
    // falling in this buffer.
    //
    // Position comes from PatternPlayer — same source as PAT mode. In SONG
    // mode, JS sets PatternPlayer.loopLength to the full arrangement length,
    // so the position naturally wraps at song end (free looping, no JS
    // reset-on-wrap needed). Clip positions in `arrangement` are relative to
    // this same "song-local" origin.
    //
    // Playback shape: the pattern TILES inside the clip. A 1-bar pattern on
    // a 4-bar clip plays four times — matches FL/Ableton/Logic playlist
    // behavior where dragging a short loop long makes it repeat to fill.
    // Notes past the pattern's own length are still dropped (the piano roll
    // doesn't let you draw past pattern end anyway). Playback truncates at
    // the clip's end regardless of pattern length.
    void injectSongMode(juce::MidiBuffer& midi, int numSamples) {
        if (patternPlayer == nullptr) return;
        if (!transport->getIsPlaying()) return;
        if (transport->getBufferStartSample() < 0) return;  // count-in
        const std::int64_t bufStart = patternPlayer->getBufferStartPosition();
        const std::int64_t bufEnd = bufStart + numSamples;

        const juce::SpinLock::ScopedTryLockType tryLock(patternLock);
        if (!tryLock.isLocked()) return;
        if (arrangement.empty() || notesByPattern.empty()) return;

        for (const auto& clip : arrangement) {
            if (clip.patternLoopLenSamples <= 0) continue;
            const std::int64_t clipEndSong = clip.songStartSample + clip.lengthSamples;
            if (clipEndSong <= bufStart)      continue; // clip fully in the past
            if (clip.songStartSample >= bufEnd) continue; // clip fully in the future

            auto notesIt = notesByPattern.find(clip.patternId);
            if (notesIt == notesByPattern.end()) continue;
            const auto& notes = notesIt->second;
            if (notes.empty()) continue;

            // Song-time overlap between this buffer and this clip.
            const std::int64_t overlapStart = juce::jmax(bufStart, clip.songStartSample);
            const std::int64_t overlapEnd   = juce::jmin(bufEnd,   clipEndSong);

            // Convert overlap to clip-local time (0 = start of clip).
            const std::int64_t clipLocalStart = overlapStart - clip.songStartSample;
            const std::int64_t clipLocalEnd   = overlapEnd   - clip.songStartSample;
            const std::int64_t patLen = clip.patternLoopLenSamples;

            // Walk every tile of the pattern that overlaps this buffer. For a
            // 1-bar pattern on a 4-bar clip that's typically 1 tile per buffer
            // (buffers are much smaller than a bar), but the loop handles the
            // rare cross-tile-boundary case cleanly.
            const std::int64_t firstTile = clipLocalStart / patLen;
            const std::int64_t lastTile  = (clipLocalEnd - 1) / patLen;
            for (std::int64_t tile = firstTile; tile <= lastTile; ++tile) {
                const std::int64_t tileStart = tile * patLen;
                // Pattern-local window that overlaps this buffer inside this tile.
                const std::int64_t patStart = juce::jmax((std::int64_t) 0,
                                                          clipLocalStart - tileStart);
                const std::int64_t patEnd   = juce::jmin(patLen,
                                                          clipLocalEnd - tileStart);
                if (patStart >= patEnd) continue;

                for (const auto& [_, note] : notes) {
                    if (note.atSample >= patLen) continue; // beyond pattern content
                    const std::int64_t onPat  = note.atSample;
                    const std::int64_t offPat = note.atSample + note.durationSamples;

                    if (onPat >= patStart && onPat < patEnd) {
                        // Song-time position = clip start + tile offset + note offset.
                        const std::int64_t songPos = clip.songStartSample + tileStart + onPat;
                        if (songPos < clipEndSong) {
                            midi.addEvent(juce::MidiMessage::noteOn(
                                patternMidiChannel, note.pitch, scaleVel(note.velocity)),
                                (int) (songPos - bufStart));
                        }
                    }
                    // noteOff fires if it falls before pattern-end AND before
                    // clip-end. Notes crossing a tile boundary get their tail
                    // clipped — same as their duration exceeding pattern length.
                    if (offPat >= patStart && offPat < patEnd) {
                        const std::int64_t songPos = clip.songStartSample + tileStart + offPat;
                        if (songPos < clipEndSong) {
                            midi.addEvent(juce::MidiMessage::noteOff(
                                patternMidiChannel, note.pitch),
                                (int) (songPos - bufStart));
                        }
                    }
                }
            }
        }
    }
};

// Stereo passthrough processor used for mixer insert BUSES. Multiple source
// channels connect audio into a bus's input; the bus runs its own effect
// chain on the summed audio and sends the result to master (or another bus).
// Defined at namespace scope, NOT locally inside createBusChannel — a local
// class type cannot be safely handed to std::make_unique across the JUCE
// audio graph, and doing so was crashing the render-sequence builder.
class BusPassthrough : public juce::AudioProcessor {
public:
    BusPassthrough() : juce::AudioProcessor(BusesProperties()
        .withInput("In",  juce::AudioChannelSet::stereo(), true)
        .withOutput("Out", juce::AudioChannelSet::stereo(), true)) {}
    const juce::String getName() const override    { return "NastyBus"; }
    void prepareToPlay(double, int) override        {}
    void releaseResources() override                {}
    bool acceptsMidi() const override               { return false; }
    bool producesMidi() const override              { return false; }
    double getTailLengthSeconds() const override    { return 0.0; }
    // Passthrough: explicitly copy input bus → output bus in case JUCE's
    // graph doesn't use in-place processing for this node (empty processBlock
    // was silencing audio when this bus sat between the drums and the
    // output).
    void processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer&) override {
        auto inBus  = getBusBuffer(buf, true,  0);
        auto outBus = getBusBuffer(buf, false, 0);
        const int n = buf.getNumSamples();
        const int chs = juce::jmin(inBus.getNumChannels(), outBus.getNumChannels());
        for (int c = 0; c < chs; ++c)
            if (outBus.getReadPointer(c) != inBus.getReadPointer(c))
                outBus.copyFrom(c, 0, inBus, c, 0, n);
    }
    void processBlock(juce::AudioBuffer<double>& buf, juce::MidiBuffer&) override {
        auto inBus  = getBusBuffer(buf, true,  0);
        auto outBus = getBusBuffer(buf, false, 0);
        const int n = buf.getNumSamples();
        const int chs = juce::jmin(inBus.getNumChannels(), outBus.getNumChannels());
        for (int c = 0; c < chs; ++c)
            if (outBus.getReadPointer(c) != inBus.getReadPointer(c))
                outBus.copyFrom(c, 0, inBus, c, 0, n);
    }
    using AudioProcessor::processBlock;
    juce::AudioProcessorEditor* createEditor() override    { return nullptr; }
    bool hasEditor() const override                        { return false; }
    int getNumPrograms() override                          { return 1; }
    int getCurrentProgram() override                       { return 0; }
    void setCurrentProgram(int) override                   {}
    const juce::String getProgramName(int) override        { return {}; }
    void changeProgramName(int, const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override  {}
    void setStateInformation(const void*, int) override    {}
};

// Real audio-level gain node. One instance per channel sits at the tail of
// the channel's audio chain (after instrument + effects, before the target
// bus / master), so setChannelGain applies to actual audio samples rather
// than only to MIDI velocity. That fixes soundfont-based instruments whose
// per-note dynamics don't map cleanly to loudness — velocity-scaling made
// their volume slider feel dead, applyGain on the buffer doesn't.
class AudioGain : public juce::AudioProcessor {
public:
    std::atomic<float> gain{1.0f};

    AudioGain() : juce::AudioProcessor(BusesProperties()
        .withInput("In",  juce::AudioChannelSet::stereo(), true)
        .withOutput("Out", juce::AudioChannelSet::stereo(), true)) {}
    const juce::String getName() const override    { return "NastyGain"; }
    void prepareToPlay(double, int) override        {}
    void releaseResources() override                {}
    bool acceptsMidi() const override               { return false; }
    bool producesMidi() const override              { return false; }
    double getTailLengthSeconds() const override    { return 0.0; }
    void processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer&) override {
        auto inBus  = getBusBuffer(buf, true,  0);
        auto outBus = getBusBuffer(buf, false, 0);
        const int n = buf.getNumSamples();
        const int chs = juce::jmin(inBus.getNumChannels(), outBus.getNumChannels());
        const float g = gain.load(std::memory_order_relaxed);
        for (int c = 0; c < chs; ++c) {
            if (outBus.getReadPointer(c) != inBus.getReadPointer(c))
                outBus.copyFrom(c, 0, inBus, c, 0, n);
            outBus.applyGain(c, 0, n, g);
        }
    }
    void processBlock(juce::AudioBuffer<double>& buf, juce::MidiBuffer&) override {
        auto inBus  = getBusBuffer(buf, true,  0);
        auto outBus = getBusBuffer(buf, false, 0);
        const int n = buf.getNumSamples();
        const int chs = juce::jmin(inBus.getNumChannels(), outBus.getNumChannels());
        const double g = (double) gain.load(std::memory_order_relaxed);
        for (int c = 0; c < chs; ++c) {
            if (outBus.getReadPointer(c) != inBus.getReadPointer(c))
                outBus.copyFrom(c, 0, inBus, c, 0, n);
            outBus.applyGain(c, 0, n, g);
        }
    }
    using AudioProcessor::processBlock;
    juce::AudioProcessorEditor* createEditor() override    { return nullptr; }
    bool hasEditor() const override                        { return false; }
    int getNumPrograms() override                          { return 1; }
    int getCurrentProgram() override                       { return 0; }
    void setCurrentProgram(int) override                   {}
    const juce::String getProgramName(int) override        { return {}; }
    void changeProgramName(int, const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override  {}
    void setStateInformation(const void*, int) override    {}
};


// Play head backed by the Transport. Plugins call getPosition() from the
// audio thread every buffer to sync arps, delays, LFOs. We read atomic values
// straight off the Transport — no lock, no allocation, safe from the audio
// thread. VST3 in particular needs a real tempo (a 0/uninitialised BPM makes
// Serato Sample and other slicers freeze); AU tends to fall back to 120.
class NastyPlayHead : public juce::AudioPlayHead {
public:
    explicit NastyPlayHead(const Transport& t) : transport(t) {}
    juce::Optional<PositionInfo> getPosition() const override {
        const auto sample   = transport.getCurrentSample();
        const auto sr       = transport.getSampleRate();
        const auto bpm      = transport.getTempoBpm();
        const double seconds = sr > 0.0 ? (double) sample / sr : 0.0;
        const double ppq     = seconds * (bpm / 60.0);

        PositionInfo info;
        info.setBpm(bpm);
        info.setTimeSignature(TimeSignature{4, 4});
        info.setIsPlaying(transport.getIsPlaying());
        info.setIsRecording(false);
        info.setIsLooping(transport.getLoopLengthSamples() > 0);
        info.setTimeInSamples(sample);
        info.setTimeInSeconds(seconds);
        info.setPpqPosition(ppq);
        info.setPpqPositionOfLastBarStart(std::floor(ppq / 4.0) * 4.0);
        return info;
    }
private:
    const Transport& transport;
};
} // namespace

// A native window that owns a plugin's AudioProcessorEditor. Deletes itself
// asynchronously when the user clicks the close button so the host can
// forget the map entry on the next message-loop tick (avoiding
// use-after-free from inside closeButtonPressed).
class PluginHost::PluginWindow : public juce::DocumentWindow {
public:
    PluginWindow(const juce::String& title, juce::AudioProcessorEditor* editor,
                 std::function<void()> onClose)
        : DocumentWindow(title, juce::Colour(0xff2b2f36),
                         juce::DocumentWindow::minimiseButton | juce::DocumentWindow::closeButton),
          closeCallback(std::move(onClose)) {
        setUsingNativeTitleBar(true);
        setContentOwned(editor, /*resizeToFit*/ true);
        setResizable(editor->isResizable(), false);
        centreWithSize(getWidth(), getHeight());
        // Float above the DAW window so it stays visible while the user types
        // notes into Nasty (which needs keyboard focus to send MIDI).
        setAlwaysOnTop(true);
        setVisible(true);
        toFront(true);
    }

    void closeButtonPressed() override {
        if (closeCallback) juce::MessageManager::callAsync(closeCallback);
    }

private:
    std::function<void()> closeCallback;
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PluginWindow)
};

PluginHost::PluginHost() {
    juce::addDefaultFormatsToManager(formatManager);
    // Separate format manager for audio-clip WAV reading — doesn't need the
    // VST3/AU host formats, just the audio-file readers.
    clipFormatManager.registerBasicFormats();

    // Publish a Transport-backed play head so tempo-syncing plugins have live
    // host transport info. AudioProcessorGraph forwards it to child nodes.
    playHead = std::make_unique<NastyPlayHead>(transport);
    graph.setPlayHead(playHead.get());

    // Add I/O nodes to the graph (input unused for MVP, output routes to speakers).
    graph.addNode(std::make_unique<Graph::AudioGraphIOProcessor>(
        Graph::AudioGraphIOProcessor::audioInputNode));
    auto outNode = graph.addNode(std::make_unique<Graph::AudioGraphIOProcessor>(
        Graph::AudioGraphIOProcessor::audioOutputNode));
    graph.addNode(std::make_unique<Graph::AudioGraphIOProcessor>(
        Graph::AudioGraphIOProcessor::midiInputNode));
    graph.addNode(std::make_unique<Graph::AudioGraphIOProcessor>(
        Graph::AudioGraphIOProcessor::midiOutputNode));

    // Engine-hosted metronome node added to the graph. The metronome->out
    // connection is deferred to startAudio() — before the audio device
    // opens, outNode reports zero output channels and addConnection fails.
    metronomeNode = graph.addNode(std::make_unique<Metronome>(transport));
}

PluginHost::~PluginHost() { stopAudio(); }

// Audio callback wrapper — advances Transport around the graph render.
// Called by JUCE on the audio thread at buffer rate. Real-time safe: no
// allocations, no locks, only atomic loads/stores on the Transport.
void PluginHost::audioDeviceIOCallbackWithContext(const float* const* inputChannelData,
                                                  int numInputChannels,
                                                  float* const* outputChannelData,
                                                  int numOutputChannels,
                                                  int numSamples,
                                                  const juce::AudioIODeviceCallbackContext& context) {
    transport.beginBuffer(numSamples);
    patternPlayer.beginBuffer(numSamples, transport);
    juce::AudioProcessorPlayer::audioDeviceIOCallbackWithContext(
        inputChannelData, numInputChannels,
        outputChannelData, numOutputChannels,
        numSamples, context);
    // Tap the input side to disk if recording is armed. writeFromFloatArrays
    // blocks briefly on the audio thread — that's acceptable for a single
    // mic at 48kHz; if it starts costing us buffer under-runs, wrap in a
    // ThreadedWriter with lock-free FIFO.
    if (recordingActive.load(std::memory_order_acquire)
        && recordingWriter != nullptr
        && numInputChannels > 0
        && inputChannelData != nullptr) {
        recordingWriter->writeFromFloatArrays(inputChannelData,
                                              numInputChannels,
                                              numSamples);
        recordingSamples.fetch_add(numSamples, std::memory_order_relaxed);
    }
    transport.endBuffer();
    patternPlayer.endBuffer();
}

void PluginHost::audioDeviceAboutToStart(juce::AudioIODevice* device) {
    if (device != nullptr) {
        transport.setSampleRate(device->getCurrentSampleRate());
    }
    juce::AudioProcessorPlayer::audioDeviceAboutToStart(device);
}

void PluginHost::audioDeviceStopped() {
    juce::AudioProcessorPlayer::audioDeviceStopped();
}

void PluginHost::setMetronomeEnabled(bool v) {
    if (!metronomeNode) return;
    if (auto* m = dynamic_cast<Metronome*>(metronomeNode->getProcessor())) {
        m->setEnabled(v);
    }
}

// Add a MidiInjector to the graph and wire its transport pointer. Every
// channel creation path funnels through here — pattern playback works the
// same for plugin channels, GM channels, and drum-sample channels.
juce::AudioProcessorGraph::Node::Ptr PluginHost::addInjectorNode() {
    auto injector = std::make_unique<MidiInjector>();
    injector->transport = &transport;
    injector->patternPlayer = &patternPlayer;
    injector->patternMidiChannel = 1;
    return graph.addNode(std::move(injector));
}

juce::AudioProcessorGraph::Node::Ptr PluginHost::addGainNode() {
    return graph.addNode(std::make_unique<AudioGain>());
}

void PluginHost::scanDefaultPaths(const ScanProgress& onProgress) {
    // deadMansFile: if a plugin crashes mid-scan, its path gets written here
    // BEFORE the crash. Next scan skips anything already in the file — so one
    // bad plugin can never take down the whole engine on boot again.
    auto supportDir = juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory)
        .getChildFile("nasty");
    supportDir.createDirectory();
    auto deadMans = supportDir.getChildFile("scan-crashes.txt");

    for (int i = 0; i < formatManager.getNumFormats(); ++i) {
        auto* format = formatManager.getFormat(i);
        auto searchPaths = format->getDefaultLocationsToSearch();

        // Also scan a bundled-with-app instruments folder if the parent
        // process points us at one (via NASTY_INSTRUMENTS_PATH). Lets Nasty
        // ship Sfizz + curated sample libraries in the .dmg with zero
        // install work for the user.
        if (const char* extra = std::getenv("NASTY_INSTRUMENTS_PATH")) {
            juce::File extraDir(juce::String::fromUTF8(extra));
            if (extraDir.isDirectory()) {
                searchPaths.add(extraDir);
            }
        }

        juce::PluginDirectoryScanner scanner(
            knownPlugins, *format, searchPaths,
            /*recursive*/ true, deadMans);

        juce::String nameBeingScanned;
        int idx = 0, total = (int)knownPlugins.getNumTypes();
        while (scanner.scanNextFile(true, nameBeingScanned)) {
            if (onProgress) onProgress(nameBeingScanned, ++idx, total);
        }
    }
}

bool PluginHost::loadPluginCache(const juce::File& cacheFile) {
    if (!cacheFile.existsAsFile()) return false;
    auto xml = juce::XmlDocument::parse(cacheFile);
    if (!xml) return false;
    knownPlugins.recreateFromXml(*xml);
    return knownPlugins.getNumTypes() > 0;
}

void PluginHost::savePluginCache(const juce::File& cacheFile) const {
    cacheFile.getParentDirectory().createDirectory();
    auto xml = knownPlugins.createXml();
    if (xml) xml->writeTo(cacheFile);
}

size_t PluginHost::pluginCount() const { return (size_t) knownPlugins.getNumTypes(); }

juce::var PluginHost::pluginListAsJson() const {
    juce::Array<juce::var> arr;
    // Nasty-native effects appear at the top of the manifest so the UI's
    // plugin picker surfaces them alongside VST3/AU plugins without any
    // extra frontend work.
    {
        auto* d = new juce::DynamicObject();
        d->setProperty("id",           juce::var("nasty:ducker"));
        d->setProperty("name",         juce::var("NastyDucker"));
        d->setProperty("format",       juce::var("Nasty"));
        d->setProperty("manufacturer", juce::var("Nasty"));
        d->setProperty("category",     juce::var("Fx|Dynamics"));
        d->setProperty("isInstrument", juce::var(false));
        d->setProperty("presets",      juce::var(juce::Array<juce::var>{}));
        arr.add(juce::var(d));
    }
    for (const auto& t : knownPlugins.getTypes()) {
        auto* o = new juce::DynamicObject();
        const auto id = t.createIdentifierString();
        o->setProperty("id",           id);
        o->setProperty("name",         t.name);
        o->setProperty("format",       t.pluginFormatName);
        o->setProperty("manufacturer", t.manufacturerName);
        o->setProperty("category",     t.category);
        o->setProperty("isInstrument", t.isInstrument);
        // Preset (program) names — the AI reads these to pick "Wobble Bass"
        // style patches by name. Missing key = "not scanned yet"; empty
        // array = "scanned; plugin exposes no programs via the standard API
        // (its own patch browser is in the GUI, we can't see it from here)."
        juce::Array<juce::var> presets;
        auto it = presetsByPluginId.find(id);
        if (it != presetsByPluginId.end()) {
            for (const auto& p : it->second) presets.add(juce::var(p));
        }
        o->setProperty("presets", juce::var(presets));
        arr.add(juce::var(o));
    }
    return juce::var(arr);
}

void PluginHost::scanAllPluginPresets(const ScanProgress& onProgress) {
    // Instantiate each plugin once, query its factory program list, cache the
    // names, destroy the instance. On subsequent boots the disk cache short-
    // circuits this loop — only genuinely-new plugins take the cost.
    //
    // Called on the main thread AFTER scanDefaultPaths and BEFORE the message
    // loop starts. This is the same window scanDefaultPaths runs in, so if
    // that works this does too. A plugin that crashes during instantiation
    // would be caught by the deadMansFile from the earlier plugin scan pass.
    const int total = (int) knownPlugins.getNumTypes();
    int idx = 0;
    for (const auto& t : knownPlugins.getTypes()) {
        ++idx;
        const auto id = t.createIdentifierString();
        if (presetsByPluginId.count(id)) {
            // Already cached from a previous boot (or a previous pass).
            if (onProgress) onProgress(t.name + " (cached)", idx, total);
            continue;
        }
        if (onProgress) onProgress(t.name, idx, total);

        juce::String err;
        auto inst = formatManager.createPluginInstance(
            t, /*sampleRate*/ 44100.0, /*blockSize*/ 512, err);
        juce::StringArray names;
        if (inst != nullptr) {
            const int n = inst->getNumPrograms();
            for (int i = 0; i < n; ++i) names.add(inst->getProgramName(i));
        }
        // Store even the empty result — the key acts as a "scanned" marker
        // so we don't retry on every boot.
        presetsByPluginId[id] = names;
    }
}

bool PluginHost::loadPresetCache(const juce::File& cacheFile) {
    if (!cacheFile.existsAsFile()) return false;
    auto root = juce::JSON::parse(cacheFile);
    if (!root.isObject()) return false;
    auto* obj = root.getDynamicObject();
    if (obj == nullptr) return false;
    for (const auto& kv : obj->getProperties()) {
        juce::StringArray names;
        if (auto* arr = kv.value.getArray()) {
            for (const auto& v : *arr) names.add(v.toString());
        }
        presetsByPluginId[kv.name.toString()] = names;
    }
    return true;
}

void PluginHost::savePresetCache(const juce::File& cacheFile) const {
    cacheFile.getParentDirectory().createDirectory();
    auto* obj = new juce::DynamicObject();
    for (const auto& [id, names] : presetsByPluginId) {
        juce::Array<juce::var> arr;
        for (const auto& n : names) arr.add(juce::var(n));
        obj->setProperty(id, juce::var(arr));
    }
    cacheFile.replaceWithText(juce::JSON::toString(juce::var(obj)));
}

void PluginHost::startAudio() {
    if (audioRunning) return;

    // Initialise with room for stereo input even though we don't bind an
    // input device yet — numInputChansNeeded is stored internally and gates
    // how many input channels come through once someone picks a mic. If we
    // start at 0, later setAudioDeviceSetup calls with an input device open
    // it with 0 active channels (silent). Bluetooth headsets stay in A2DP
    // because inputDeviceName is empty — CoreAudio only flips to HFP when
    // the BT device is actually opened for input.
    juce::AudioDeviceManager::AudioDeviceSetup setup;
    setup.inputDeviceName = "";
    setup.useDefaultInputChannels = false;
    setup.inputChannels.clear();
    setup.useDefaultOutputChannels = true;
    juce::String err = deviceManager.initialise(
        /*numInputs*/  2,
        /*numOutputs*/ 2,
        /*savedState*/ nullptr,
        /*selectDefaultDevice*/ true,
        /*preferredDefault*/ juce::String(),
        &setup);
    if (err.isNotEmpty()) {
        std::cerr << "[PluginHost] audio init failed: " << err << std::endl;
        return;
    }

    // Trust the system default. User picks what they want from the dropdown.
    // We only WARN (via the sample-rate readout in the toolbar) if the rate
    // looks too low to play music — we never switch silently.

    // If the device came up at a music-hostile rate (Bluetooth hands-free
    // mode = 16/24kHz), try to force it back to 48000. If CoreAudio can't
    // honor the request, the front end's warning modal fires and the user
    // picks a different device from the Out dropdown.
    if (auto* dev = deviceManager.getCurrentAudioDevice()) {
        if (dev->getCurrentSampleRate() < 44100.0) {
            juce::AudioDeviceManager::AudioDeviceSetup s;
            deviceManager.getAudioDeviceSetup(s);
            s.sampleRate = 48000.0;
            deviceManager.setAudioDeviceSetup(s, true);
        }
    }

    if (!deviceManager.getCurrentAudioDevice()) {
        std::cerr << "[PluginHost] no current audio device after init" << std::endl;
    }
    setProcessor(&graph);
    deviceManager.addAudioCallback(this);
    deviceManager.addMidiInputDeviceCallback({}, this);

    // Wire the metronome to the master output — now that the device is
    // open, outNode has valid output channels (before this point addConnection
    // silently fails because outNode reports 0 channels).
    if (metronomeNode) {
        auto outNode = graph.getNodeForId(Graph::NodeID(2));
        if (outNode) {
            for (int ch = 0; ch < 2; ++ch) {
                graph.addConnection({ { metronomeNode->nodeID, ch },
                                      { outNode->nodeID,       ch } });
            }
        }
    }
    // Listen for device changes so we can reconnect when macOS wakes from
    // sleep, or the user unplugs and replugs an interface. Without this the
    // engine holds a stale device handle and stays silent after wake.
    deviceManager.addChangeListener(this);
    audioRunning = true;
}

void PluginHost::changeListenerCallback(juce::ChangeBroadcaster* source) {
    if (source != &deviceManager) return;
    // If the current device went away (sleep, unplug), rebind — but preserve
    // whatever input device the user already picked. Previous behaviour called
    // initialiseWithDefaultDevices(0, 2), which silently killed the mic every
    // time the user switched output.
    auto* currentDevice = deviceManager.getCurrentAudioDevice();
    if (currentDevice && currentDevice->isOpen()) return;
    std::cerr << "[PluginHost] audio device changed / lost — reconnecting" << std::endl;

    juce::AudioDeviceManager::AudioDeviceSetup preserved;
    deviceManager.getAudioDeviceSetup(preserved);

    deviceManager.removeAudioCallback(this);
    deviceManager.initialise(/*numInputs*/ 2, /*numOutputs*/ 2,
                             /*savedState*/ nullptr,
                             /*selectDefaultDevice*/ true,
                             /*preferredDefault*/ juce::String(),
                             &preserved);
    deviceManager.addAudioCallback(this);

    // Re-run the audio-input wiring — the graph audio input node's channel
    // count may have shifted with the new device.
    std::lock_guard<std::mutex> lock(mutex);
    reconnectAudioInputsUnlocked();
}

void PluginHost::stopAudio() {
    if (!audioRunning) return;
    deviceManager.removeChangeListener(this);
    deviceManager.removeAudioCallback(this);
    deviceManager.removeMidiInputDeviceCallback({}, this);
    setProcessor(nullptr);
    audioRunning = false;
}

// Case-insensitive fuzzy match: exact match wins over substring, first
// substring hit wins over later ones. Returns -1 if nothing matches. Kept
// simple deliberately — better mismatch behaviour is Claude's job, not the
// engine's (Claude sees the whole preset list in the manifest).
static int matchPresetIndex(juce::AudioPluginInstance& inst,
                            const juce::String& presetName) {
    if (presetName.isEmpty()) return -1;
    const auto target = presetName.toLowerCase().trim();
    const int n = inst.getNumPrograms();
    int fallback = -1;
    for (int i = 0; i < n; ++i) {
        const auto p = inst.getProgramName(i).toLowerCase().trim();
        if (p == target) return i;
        if (fallback < 0 && p.contains(target)) fallback = i;
    }
    return fallback;
}

juce::String PluginHost::loadPlugin(const juce::String& channelId,
                                    const juce::String& pluginId,
                                    const juce::String& base64State,
                                    const juce::String& presetName) {
    std::cerr << "[loadPlugin] START ch=" << channelId << " pluginId=" << pluginId << std::endl;
    startAudio(); // lazy-init audio device on first plugin load

    // Find description
    const juce::PluginDescription* desc = nullptr;
    for (const auto& t : knownPlugins.getTypes()) {
        if (t.createIdentifierString() == pluginId) { desc = &t; break; }
    }
    if (!desc) {
        std::cerr << "[loadPlugin] FAIL: plugin not found in manifest" << std::endl;
        return "Plugin not found: " + pluginId;
    }
    std::cerr << "[loadPlugin] step1 found desc name=" << desc->name << " format=" << desc->pluginFormatName << std::endl;

    juce::String err;
    auto instance = formatManager.createPluginInstance(
        *desc, graph.getSampleRate(), graph.getBlockSize(), err);
    if (!instance) {
        std::cerr << "[loadPlugin] FAIL: createPluginInstance returned null err='" << err << "'" << std::endl;
        return err.isNotEmpty() ? err : juce::String("Instantiation failed");
    }
    std::cerr << "[loadPlugin] step2 created instance ok" << std::endl;

    // Publish host tempo to the plugin directly (not all wrappers pick it up
    // through the graph forwarding path — VST3 in particular reads from the
    // processor's playhead at first processBlock).
    instance->setPlayHead(playHead.get());

    // Apply previously-saved plugin state (Serato's loaded sample, Serum
    // patch, etc.). Failure is silent — a corrupt blob shouldn't block load.
    if (base64State.isNotEmpty()) {
        juce::MemoryOutputStream decoded;
        if (juce::Base64::convertFromBase64(decoded, base64State) && decoded.getDataSize() > 0) {
            std::cerr << "[loadPlugin] step3 applying saved state (" << decoded.getDataSize() << " bytes)" << std::endl;
            instance->setStateInformation(decoded.getData(), (int) decoded.getDataSize());
            std::cerr << "[loadPlugin] step3 saved state applied" << std::endl;
        }
    }

    // Preset selection AFTER any saved state (a chosen preset overrides
    // whatever the state blob restored). Silent no-op if nothing matches —
    // Claude already knows the plugin's preset list from the manifest, so
    // a "no match" here means Claude passed something the plugin doesn't
    // actually expose.
    if (presetName.isNotEmpty()) {
        const int idx = matchPresetIndex(*instance, presetName);
        std::cerr << "[loadPlugin] step4 preset '" << presetName << "' → idx=" << idx << std::endl;
        if (idx >= 0) instance->setCurrentProgram(idx);
    }

    // Everything above (createPluginInstance, state, preset) ran WITHOUT
    // holding MessageManagerLock — that's the whole point, plugin init needs
    // the message loop to pump. Now take the lock JUST for the graph mutation
    // so the async render-sequence rebuild can't race with us.
    std::cerr << "[loadPlugin] step5 acquiring MessageManagerLock for graph mutation" << std::endl;
    juce::MessageManagerLock mml;
    if (!mml.lockWasGained()) {
        std::cerr << "[loadPlugin] FAIL: MessageManagerLock aborted" << std::endl;
        return "aborted";
    }

    std::cerr << "[loadPlugin] step6 unloading existing on channel (if any)" << std::endl;
    unloadPlugin(channelId); // replace if exists

    std::cerr << "[loadPlugin] step7 adding injector + plugin + gain to graph" << std::endl;
    auto injectorNode = addInjectorNode();
    auto pluginNode   = graph.addNode(std::move(instance));
    auto gainNode     = addGainNode();
    // JUCE returns null if the graph rejects the node — happens with a few
    // pathological plugins. If we skipped this check the null Node reference
    // would sit in the graph until the next async render-sequence rebuild
    // walked it and crashed (EXC_BAD_ACCESS in getNodeMap).
    if (pluginNode == nullptr || injectorNode == nullptr || gainNode == nullptr) {
        std::cerr << "[loadPlugin] FAIL: graph rejected node (plugin=" << (pluginNode!=nullptr)
                  << " injector=" << (injectorNode!=nullptr)
                  << " gain=" << (gainNode!=nullptr) << ")" << std::endl;
        if (injectorNode) graph.removeNode(injectorNode->nodeID);
        if (pluginNode)   graph.removeNode(pluginNode->nodeID);
        if (gainNode)     graph.removeNode(gainNode->nodeID);
        return "graph rejected plugin: " + pluginId;
    }

    // MIDI: injector → plugin.
    graph.addConnection({{injectorNode->nodeID, Graph::midiChannelIndex},
                         {pluginNode->nodeID,   Graph::midiChannelIndex}});
    std::cerr << "[loadPlugin] step8 wired midi injector → plugin" << std::endl;

    {
        std::lock_guard<std::mutex> lock(mutex);
        ChannelSlot slot{ pluginNode->nodeID, injectorNode->nodeID, gainNode->nodeID, 1, {}, {}, false };
        channels[channelId] = slot;
        std::cerr << "[loadPlugin] step9 calling rewireChannelUnlocked" << std::endl;
        rewireChannelUnlocked(channels[channelId]); // instrument → output
    }
    std::cerr << "[loadPlugin] DONE ch=" << channelId << std::endl;
    return {};
}

juce::String PluginHost::addGmChannel(const juce::String& channelId,
                                      int gmProgram,
                                      const juce::String& sf2Path) {
    startAudio();

    auto gm = std::make_unique<GmSynth>();
    if (!gm->loadSoundFont(sf2Path)) {
        std::cerr << "[PluginHost] SF2 load failed: " << sf2Path << std::endl;
        return "Failed to load SoundFont: " + sf2Path;
    }
    gm->setProgram(gmProgram);

    unloadPlugin(channelId); // replace if exists

    auto injectorNode = addInjectorNode();
    auto gmNode       = graph.addNode(std::move(gm));
    auto gainNode     = addGainNode();
    if (gmNode == nullptr || injectorNode == nullptr || gainNode == nullptr) {
        if (injectorNode) graph.removeNode(injectorNode->nodeID);
        if (gmNode)       graph.removeNode(gmNode->nodeID);
        if (gainNode)     graph.removeNode(gainNode->nodeID);
        return juce::String("graph rejected GM synth");
    }

    // MIDI: injector → gm.
    graph.addConnection({{injectorNode->nodeID, Graph::midiChannelIndex},
                         {gmNode->nodeID,       Graph::midiChannelIndex}});

    {
        std::lock_guard<std::mutex> lock(mutex);
        ChannelSlot slot{ gmNode->nodeID, injectorNode->nodeID, gainNode->nodeID, 1, {}, {}, false };
        channels[channelId] = slot;
        rewireChannelUnlocked(channels[channelId]); // gm → output
    }
    return {};
}

juce::String PluginHost::addDrumChannel(const juce::String& channelId,
                                        const juce::String& samplePath,
                                        int rootNote) {
    std::cerr << "[PluginHost] add_drum ch=" << channelId
              << " sample=" << samplePath << std::endl;
    startAudio();

    auto drum = std::make_unique<SampleDrum>();
    if (!drum->loadSample(samplePath, rootNote)) {
        std::cerr << "[PluginHost] drum sample load failed: " << samplePath << std::endl;
        return "Failed to load sample: " + samplePath;
    }

    unloadPlugin(channelId);

    auto injectorNode = addInjectorNode();
    auto drumNode     = graph.addNode(std::move(drum));
    auto gainNode     = addGainNode();
    if (drumNode == nullptr || injectorNode == nullptr || gainNode == nullptr) {
        if (injectorNode) graph.removeNode(injectorNode->nodeID);
        if (drumNode)     graph.removeNode(drumNode->nodeID);
        if (gainNode)     graph.removeNode(gainNode->nodeID);
        return juce::String("graph rejected drum sampler");
    }

    // MIDI: injector → drum.
    graph.addConnection({{injectorNode->nodeID, Graph::midiChannelIndex},
                         {drumNode->nodeID,     Graph::midiChannelIndex}});

    {
        std::lock_guard<std::mutex> lock(mutex);
        ChannelSlot slot{ drumNode->nodeID, injectorNode->nodeID, gainNode->nodeID, 1, {}, {}, false };
        channels[channelId] = slot;
        rewireChannelUnlocked(channels[channelId]);
    }
    return {};
}

void PluginHost::setGmProgram(const juce::String& channelId, int gmProgram) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.pluginNodeId);
    if (!node) return;
    if (auto* gm = dynamic_cast<GmSynth*>(node->getProcessor())) {
        gm->setProgram(gmProgram);
    }
}

void PluginHost::unloadPlugin(const juce::String& channelId) {
    std::cerr << "[unloadPlugin] ch=" << channelId << std::endl;
    // Close the editor window first (on message thread) so its held editor
    // pointer doesn't dangle when we drop the plugin node below.
    hidePluginUI(channelId);

    // Also close any effect editor windows on this channel and drop their nodes.
    std::vector<juce::String> effectSlotIds;
    {
        std::lock_guard<std::mutex> lock(mutex);
        auto it = channels.find(channelId);
        if (it != channels.end()) {
            for (const auto& e : it->second.effects) effectSlotIds.push_back(e.slotId);
        }
    }
    for (const auto& sid : effectSlotIds) hideEffectUI(channelId, sid);

    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    for (const auto& e : it->second.effects) graph.removeNode(e.nodeId);
    graph.removeNode(it->second.pluginNodeId);
    graph.removeNode(it->second.injectorNodeId);
    if (it->second.gainNodeId != juce::AudioProcessorGraph::NodeID{})
        graph.removeNode(it->second.gainNodeId);
    channels.erase(it);
}

void PluginHost::resetGraph() {
    std::cerr << "[resetGraph] START" << std::endl;
    // Snapshot the channel IDs first, then unload each. unloadPlugin handles
    // editor-window teardown + graph-node removal + map erase, matching the
    // per-channel unload path exactly — reusing it keeps the two teardown
    // paths from drifting.
    std::vector<juce::String> channelIds;
    {
        std::lock_guard<std::mutex> lock(mutex);
        channelIds.reserve(channels.size());
        for (const auto& kv : channels) channelIds.push_back(kv.first);
    }
    for (const auto& id : channelIds) unloadPlugin(id);
    // Also tear down any audio clips — a fresh song hydrate re-adds them
    // via add_audio_clip commands.
    {
        std::lock_guard<std::mutex> lock(mutex);
        for (auto& kv : audioClips) graph.removeNode(kv.second.nodeId);
        audioClips.clear();
    }
    std::cerr << "[resetGraph] DONE — cleared " << channelIds.size()
              << " channels" << std::endl;
}

// Rebuild the audio graph for one channel. Called after any effect-chain
// mutation (add/remove/reorder/bypass) or after routing changes.  Must be
// called with `mutex` held.
//
// Chain shape: source → eff[0] → eff[1] → ... → target.  Bypassed effects
// are skipped (the audio flows around them). Target = master out by default,
// or the input node of another channel (bus routing) if targetChannelId is
// set.
void PluginHost::rewireChannelUnlocked(ChannelSlot& slot) {
    std::cerr << "[rewire] START pluginNode=" << slot.pluginNodeId.uid
              << " injector=" << slot.injectorNodeId.uid
              << " effects=" << slot.effects.size()
              << " target='" << slot.targetChannelId << "'" << std::endl;
    auto outNode = graph.getNodeForId(Graph::NodeID(2));
    if (!outNode) {
        std::cerr << "[rewire] BAIL: no outNode (nodeID 2)" << std::endl;
        return;
    }

    // Pause the audio thread while we mutate the graph — otherwise the
    // render-sequence rebuild races with our add/remove calls and can
    // dereference a Node whose processor hasn't been wired in yet (SIGSEGV).
    graph.suspendProcessing(true);

    // Snapshot connections first — removing while iterating the live list
    // would invalidate our iterator on some JUCE versions.
    auto conns = graph.getConnections();

    auto isChannelNode = [&](Graph::NodeID nid) {
        if (nid == slot.pluginNodeId) return true;
        if (nid == slot.gainNodeId)   return true;
        for (const auto& e : slot.effects) {
            if (nid == e.nodeId) return true;
            if (nid == e.wetGainNodeId) return true;
            if (nid == e.dryGainNodeId) return true;
        }
        return false;
    };

    // Resolve the MAIN audio route. Priority:
    //   1. First entry in sends[] with targetInput == "main"
    //   2. Legacy targetChannelId (only if sends[] is completely empty —
    //      preserves old behaviour for channels that never got sends)
    //   3. master_bus default (only if NO routing intent has been expressed
    //      at all — sends empty AND targetChannelId empty)
    // If the user has explicitly populated sends[] but removed every main
    // entry, targetNodeId stays invalid → we skip the main output-connection
    // add below. Result: strip is silent, matching FL's "disconnected" state.
    Graph::NodeID targetNodeId;  // invalid = no main output
    juce::String resolvedTargetId;
    for (const auto& s : slot.sends) {
        if (s.targetInput == "main" && s.targetChannelId.isNotEmpty()) {
            resolvedTargetId = s.targetChannelId;
            break;
        }
    }
    // Fallback rule differs by slot type:
    //   - master_bus (isBus + is-master): route to raw audio output
    //   - other buses (isBus + not master): NO fallback. Empty sends = silent.
    //     Buses carry explicit routing via sends[]; an empty sends list
    //     means the user unplugged them.
    //   - channels (not buses): use targetChannelId; if empty, fall back
    //     to master_bus. Channels don't use sends[] in current data model.
    if (resolvedTargetId.isEmpty() && !slot.isBus
        && slot.targetChannelId.isNotEmpty()) {
        resolvedTargetId = slot.targetChannelId;
    }
    if (resolvedTargetId.isNotEmpty()) {
        auto it = channels.find(resolvedTargetId);
        if (it != channels.end()) targetNodeId = it->second.pluginNodeId;
    } else {
        auto masterIt = channels.find("master_bus");
        const bool isMasterBus = (masterIt != channels.end()
                                  && &slot == &masterIt->second);
        if (isMasterBus) {
            // Master's job is to be the sink — always route to raw output.
            targetNodeId = outNode->nodeID;
        } else if (!slot.isBus) {
            // Channel with no explicit routing → default to master.
            if (masterIt != channels.end()) {
                targetNodeId = masterIt->second.pluginNodeId;
            } else {
                targetNodeId = outNode->nodeID;
            }
        }
        // Bus (not master) with no explicit sends: targetNodeId stays
        // invalid → silent. Deliberate.
    }

    for (const auto& c : conns) {
        // Only tear down the OUTPUT side of this channel's chain — where the
        // source is one of this channel's nodes and destination is either
        // another of this channel's nodes, or the master output, or any
        // OTHER channel's input (in case we're changing routing target).
        if (c.source.channelIndex == Graph::midiChannelIndex) continue;
        if (!isChannelNode(c.source.nodeID)) continue;
        graph.removeConnection(c);
    }

    // Reconnect: source → each active effect (via wet/dry wrap) → gain → target.
    // Each active effect uses parallel routing: prev feeds both the plugin
    // (wet path) and the dryGain node (dry path). Both wetGain and dryGain
    // outputs then feed the NEXT stage's input, where JUCE's graph auto-sums
    // multiple inputs into one target. `prevs` tracks the current set of
    // outputs — usually one, but two while walking between wet/dry-wrapped
    // effects. Legacy effects with no wet/dry nodes fall back to serial.
    std::vector<Graph::NodeID> prevs = { slot.pluginNodeId };
    for (auto& e : slot.effects) {
        if (e.bypassed) continue;
        const bool hasWrap = (e.wetGainNodeId != Graph::NodeID{}
                           && e.dryGainNodeId != Graph::NodeID{});
        for (auto srcId : prevs) {
            for (int ch = 0; ch < 2; ++ch) {
                // Wet path: prev → plugin input
                graph.addConnection({{srcId, ch}, {e.nodeId, ch}});
                // Dry path (only if wrap is present): prev → dryGain input
                if (hasWrap) {
                    graph.addConnection({{srcId, ch}, {e.dryGainNodeId, ch}});
                }
            }
        }
        if (hasWrap) {
            // Wet path continues: plugin output → wetGain
            for (int ch = 0; ch < 2; ++ch) {
                graph.addConnection({{e.nodeId, ch}, {e.wetGainNodeId, ch}});
            }
            prevs = { e.wetGainNodeId, e.dryGainNodeId };
        } else {
            prevs = { e.nodeId };
        }
    }
    // Route through the channel's own audio gain stage before the target so
    // setChannelGain applies to actual audio samples. Legacy slots without a
    // gain node fall back to direct-to-target wiring.
    Graph::NodeID prev;
    if (slot.gainNodeId != Graph::NodeID{}) {
        for (auto srcId : prevs) {
            for (int ch = 0; ch < 2; ++ch) {
                graph.addConnection({{srcId, ch}, {slot.gainNodeId, ch}});
            }
        }
        prev = slot.gainNodeId;
    } else {
        // No gain node — very legacy path. Sends and target routing below
        // want a single scalar `prev`; if we have multiple parallel outputs
        // here we collapse by using the first (works but bypasses summing).
        // In practice every channel has a gain node.
        prev = prevs.empty() ? slot.pluginNodeId : prevs.front();
    }
    // Only wire the main output if we actually resolved a target. When the
    // user has explicitly emptied their main sends, targetNodeId stays
    // invalid and this loop is skipped — the strip goes silent, matching
    // FL's "unplugged" state.
    if (targetNodeId != Graph::NodeID{}) {
        for (int ch = 0; ch < 2; ++ch) {
            graph.addConnection({{prev, ch}, {targetNodeId, ch}});
        }
    }
    // Post-fader sends. Every send taps `prev` (which points at the gain node
    // if the channel has one, otherwise the last effect / instrument). For
    // sidechain sends we walk the target bus's effect chain, find the first
    // plugin that reports 4+ input channels, and hit its channels 2/3 —
    // JUCE routes those to input bus 1 (the sidechain bus). Silent no-op if
    // no such plugin exists; the send re-wires on the next rewire pass, so
    // dropping a compressor onto the target strip later picks it up.
    // Additional sends: sidechain, plus main sends beyond the primary one
    // that was already consumed above as the resolved target. Skip the first
    // main send we encounter (it drove targetNodeId); wire second+ as
    // fan-out connections.
    bool firstMainConsumed = false;
    for (const auto& s : slot.sends) {
        if (s.targetChannelId.isEmpty()) continue;
        auto tgtIt = channels.find(s.targetChannelId);
        if (tgtIt == channels.end()) continue;
        if (s.targetInput == "sidechain") {
            Graph::NodeID scNode;
            for (const auto& eff : tgtIt->second.effects) {
                if (eff.bypassed) continue;
                auto effNode = graph.getNodeForId(eff.nodeId);
                if (!effNode) continue;
                auto* proc = effNode->getProcessor();
                if (!proc) continue;
                if (proc->getTotalNumInputChannels() >= 4) {
                    scNode = eff.nodeId;
                    break;
                }
            }
            if (scNode != Graph::NodeID{}) {
                graph.addConnection({{prev, 0}, {scNode, 2}});
                graph.addConnection({{prev, 1}, {scNode, 3}});
                std::cerr << "[rewire] send SC → " << s.targetChannelId
                          << " node=" << scNode.uid << std::endl;
            } else {
                std::cerr << "[rewire] SC send to " << s.targetChannelId
                          << " deferred — no 4-in plugin on target yet" << std::endl;
            }
        } else {
            // "main" send. Skip the first — it's already wired as the
            // primary route via the targetNodeId above. Additional main
            // sends fan the signal out to more destinations.
            if (!firstMainConsumed) {
                firstMainConsumed = true;
                continue;
            }
            for (int ch = 0; ch < 2; ++ch) {
                graph.addConnection({{prev, ch}, {tgtIt->second.pluginNodeId, ch}});
            }
        }
    }
    std::cerr << "[rewire] DONE target=" << targetNodeId.uid << std::endl;

    graph.suspendProcessing(false);
}

juce::String PluginHost::createBusChannel(const juce::String& channelId) {
    startAudio();
    auto node     = graph.addNode(std::make_unique<BusPassthrough>());
    auto gainNode = addGainNode();
    if (node == nullptr || gainNode == nullptr) {
        if (node)     graph.removeNode(node->nodeID);
        if (gainNode) graph.removeNode(gainNode->nodeID);
        return juce::String("graph rejected bus passthrough");
    }

    std::lock_guard<std::mutex> lock(mutex);
    // Replace existing bus with same id (idempotent create).
    auto existing = channels.find(channelId);
    if (existing != channels.end()) {
        for (const auto& e : existing->second.effects) graph.removeNode(e.nodeId);
        graph.removeNode(existing->second.pluginNodeId);
        if (existing->second.injectorNodeId != juce::AudioProcessorGraph::NodeID{})
            graph.removeNode(existing->second.injectorNodeId);
        if (existing->second.gainNodeId != juce::AudioProcessorGraph::NodeID{})
            graph.removeNode(existing->second.gainNodeId);
        channels.erase(existing);
    }
    ChannelSlot slot{ node->nodeID, juce::AudioProcessorGraph::NodeID{}, gainNode->nodeID, 1, {}, {}, true };
    channels[channelId] = slot;
    rewireChannelUnlocked(channels[channelId]);
    return {};
}

void PluginHost::setChannelTarget(const juce::String& channelId, const juce::String& targetChannelId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    if (it->second.targetChannelId == targetChannelId) return;
    it->second.targetChannelId = targetChannelId;
    rewireChannelUnlocked(it->second);
}

juce::String PluginHost::setChannelSend(const juce::String& channelId,
                                        const juce::String& sendId,
                                        const juce::String& targetChannelId,
                                        const juce::String& targetInput) {
    // Reject half-formed sends at the door — an empty targetChannelId in
    // sends[] otherwise looks like "explicit routing intent" but resolves to
    // nowhere, silently killing the strip. If the caller wants to remove a
    // send they should send remove_channel_send, not set with empty target.
    if (sendId.isEmpty() || targetChannelId.isEmpty()) {
        return "send needs a sendId + non-empty targetChannelId";
    }
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return "no such channel: " + channelId;

    auto& sends = it->second.sends;
    auto existing = std::find_if(sends.begin(), sends.end(),
        [&](const SendSlot& s) { return s.sendId == sendId; });
    if (existing != sends.end()) sends.erase(existing);
    sends.push_back({ sendId, targetChannelId,
                      targetInput.isEmpty() ? juce::String("main") : targetInput });
    rewireChannelUnlocked(it->second);
    return {};
}

void PluginHost::removeChannelSend(const juce::String& channelId,
                                   const juce::String& sendId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto& sends = it->second.sends;
    auto existing = std::find_if(sends.begin(), sends.end(),
        [&](const SendSlot& s) { return s.sendId == sendId; });
    if (existing == sends.end()) return;
    sends.erase(existing);
    rewireChannelUnlocked(it->second);
}

void PluginHost::rewireSendSourcesToUnlocked(const juce::String& targetChannelId) {
    for (auto& kv : channels) {
        auto& src = kv.second;
        bool touches = std::any_of(src.sends.begin(), src.sends.end(),
            [&](const SendSlot& s) { return s.targetChannelId == targetChannelId; });
        if (touches) rewireChannelUnlocked(src);
    }
}

juce::String PluginHost::addEffect(const juce::String& channelId,
                                   const juce::String& slotId,
                                   const juce::String& pluginId,
                                   const juce::String& base64State,
                                   const juce::String& presetName) {
    std::cerr << "[addEffect] START ch=" << channelId << " slot=" << slotId << " pluginId=" << pluginId << std::endl;

    // Nasty-native effects come from a small internal list, not from the
    // VST3/AU manifest. Route them through their own factory so they load
    // without a plugin scan and their bus layout (including our sidechain
    // ducker's aux input) comes up exactly as we declared it.
    std::unique_ptr<juce::AudioProcessor> instance;
    if (pluginId == "nasty:ducker") {
        instance = std::make_unique<NastyDucker>();
        // Force-enable the sidechain bus. Without this, some hosts / graph
        // configurations negotiate it to disabled and detection fails.
        if (instance->getBusCount(true) > 1) {
            auto* sc = instance->getBus(true, 1);
            if (sc && sc->isEnabled() == false) {
                sc->setCurrentLayout(juce::AudioChannelSet::stereo());
            }
        }
        std::cerr << "[addEffect] internal NastyDucker instantiated (in="
                  << instance->getTotalNumInputChannels() << ")" << std::endl;
    } else {
        const juce::PluginDescription* desc = nullptr;
        for (const auto& t : knownPlugins.getTypes()) {
            if (t.createIdentifierString() == pluginId) { desc = &t; break; }
        }
        if (!desc) {
            std::cerr << "[addEffect] FAIL: plugin not found in manifest" << std::endl;
            return "Plugin not found: " + pluginId;
        }
        std::cerr << "[addEffect] step1 found desc name=" << desc->name << " format=" << desc->pluginFormatName << std::endl;

        // Create instance WITHOUT holding MessageManagerLock — plugin init needs
        // the message loop to pump (Cocoa callbacks, plugin-internal callAsync).
        // Holding the lock across this call deadlocks the engine on slow plugins.
        juce::String err;
        instance = formatManager.createPluginInstance(
            *desc, graph.getSampleRate(), graph.getBlockSize(), err);
        if (!instance) {
            std::cerr << "[addEffect] FAIL: createPluginInstance returned null err='" << err << "'" << std::endl;
            return err.isNotEmpty() ? err : juce::String("Instantiation failed");
        }
    }
    std::cerr << "[addEffect] step2 created instance ok" << std::endl;
    instance->setPlayHead(playHead.get());

    // Attempt to enable any input buses beyond the primary one (typically the
    // sidechain input on compressors / limiters). Plugins that don't have
    // extra buses no-op silently. This lets a later set_channel_send with
    // targetInput="sidechain" find channels 2/3 to hit on this node.
    for (int i = 1; i < instance->getBusCount(true); ++i) {
        auto* bus = instance->getBus(true, i);
        if (bus == nullptr) continue;
        auto layout = bus->getDefaultLayout();
        if (layout.isDisabled()) layout = juce::AudioChannelSet::stereo();
        bus->setCurrentLayout(layout);
    }

    if (base64State.isNotEmpty()) {
        juce::MemoryOutputStream decoded;
        if (juce::Base64::convertFromBase64(decoded, base64State) && decoded.getDataSize() > 0) {
            instance->setStateInformation(decoded.getData(), (int) decoded.getDataSize());
        }
    }

    if (presetName.isNotEmpty()) {
        // Preset matching only applies to real VST3/AU plugins (which are
        // AudioPluginInstance under the hood). Nasty-native processors have
        // one program and no preset library, so skip.
        if (auto* pi = dynamic_cast<juce::AudioPluginInstance*>(instance.get())) {
            const int idx = matchPresetIndex(*pi, presetName);
            if (idx >= 0) pi->setCurrentProgram(idx);
        }
    }

    // Now take MessageManagerLock for the graph mutation portion only.
    std::cerr << "[addEffect] step3 acquiring MessageManagerLock" << std::endl;
    juce::MessageManagerLock mml;
    if (!mml.lockWasGained()) {
        std::cerr << "[addEffect] FAIL: MessageManagerLock aborted" << std::endl;
        return "aborted";
    }

    auto effectNode = graph.addNode(std::move(instance));
    if (effectNode == nullptr) {
        std::cerr << "[addEffect] FAIL: graph rejected effect node" << std::endl;
        return "graph rejected effect: " + pluginId;
    }
    std::cerr << "[addEffect] step4 added node to graph" << std::endl;

    // Create the FLOW-owned wet/dry wrap for this slot. Two gain nodes in
    // parallel — wetGain multiplied by wetDry, dryGain by 1 - wetDry. The
    // rewire pass reads both to build the parallel topology. Default is 100%
    // wet, matching the previous no-wrap behaviour so nothing changes
    // audibly until the user turns the knob down.
    auto wetGainNode = addGainNode();
    auto dryGainNode = addGainNode();
    if (wetGainNode == nullptr || dryGainNode == nullptr) {
        std::cerr << "[addEffect] FAIL: graph rejected wet/dry gain nodes" << std::endl;
        if (wetGainNode) graph.removeNode(wetGainNode->nodeID);
        if (dryGainNode) graph.removeNode(dryGainNode->nodeID);
        graph.removeNode(effectNode->nodeID);
        return juce::String("graph rejected wet/dry gain nodes");
    }
    if (auto* wp = dynamic_cast<AudioGain*>(wetGainNode->getProcessor()))
        wp->gain.store(1.0f);
    if (auto* dp = dynamic_cast<AudioGain*>(dryGainNode->getProcessor()))
        dp->gain.store(0.0f);

    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) {
        std::cerr << "[addEffect] FAIL: channel not found: " << channelId << std::endl;
        graph.removeNode(effectNode->nodeID);
        graph.removeNode(wetGainNode->nodeID);
        graph.removeNode(dryGainNode->nodeID);
        return "Channel not found: " + channelId;
    }
    // Replace if a slot with this id already exists (idempotent add). Keep
    // the existing wet/dry gain nodes if the slot already had them so the
    // user's chosen mix survives a plugin swap; only create new wrap nodes
    // for legacy slots (pre-wet/dry-wrap era) that lack them.
    for (auto& e : it->second.effects) {
        if (e.slotId == slotId) {
            graph.removeNode(e.nodeId);
            e.nodeId = effectNode->nodeID;
            e.bypassed = false;
            if (e.wetGainNodeId == Graph::NodeID{} || e.dryGainNodeId == Graph::NodeID{}) {
                // Adopt the freshly-created wrap nodes and seed them from
                // whatever wetDry the slot already had (defaults to 1.0).
                e.wetGainNodeId = wetGainNode->nodeID;
                e.dryGainNodeId = dryGainNode->nodeID;
                if (auto* wp = dynamic_cast<AudioGain*>(wetGainNode->getProcessor()))
                    wp->gain.store(e.wetDry);
                if (auto* dp = dynamic_cast<AudioGain*>(dryGainNode->getProcessor()))
                    dp->gain.store(1.0f - e.wetDry);
            } else {
                // Slot already had wrap nodes — discard the freshly-created
                // spares so we don't leak them into the graph.
                graph.removeNode(wetGainNode->nodeID);
                graph.removeNode(dryGainNode->nodeID);
            }
            rewireChannelUnlocked(it->second);
            std::cerr << "[addEffect] DONE (replaced existing slot)" << std::endl;
            return {};
        }
    }
    it->second.effects.push_back({
        slotId, effectNode->nodeID,
        wetGainNode->nodeID, dryGainNode->nodeID,
        false, 1.0f
    });
    rewireChannelUnlocked(it->second);
    // Loading a new effect on this bus may have introduced a 4-in plugin
    // (compressor with sidechain). Any deferred sidechain sends into this
    // bus need to re-attach; find them and re-rewire their sources.
    rewireSendSourcesToUnlocked(channelId);
    std::cerr << "[addEffect] DONE ch=" << channelId << std::endl;
    return {};
}

void PluginHost::removeEffect(const juce::String& channelId, const juce::String& slotId) {
    hideEffectUI(channelId, slotId);
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto& fx = it->second.effects;
    auto found = std::find_if(fx.begin(), fx.end(),
                              [&](const EffectSlot& e) { return e.slotId == slotId; });
    if (found == fx.end()) return;
    if (found->wetGainNodeId != Graph::NodeID{}) graph.removeNode(found->wetGainNodeId);
    if (found->dryGainNodeId != Graph::NodeID{}) graph.removeNode(found->dryGainNodeId);
    graph.removeNode(found->nodeId);
    fx.erase(found);
    rewireChannelUnlocked(it->second);
    // Removing the target's sidechain-capable plugin means any incoming SC
    // sends need to find the next candidate (or park until one shows up).
    rewireSendSourcesToUnlocked(channelId);
}

void PluginHost::reorderEffects(const juce::String& channelId, const juce::StringArray& newOrder) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    std::vector<EffectSlot> reordered;
    reordered.reserve(it->second.effects.size());
    for (const auto& sid : newOrder) {
        auto found = std::find_if(it->second.effects.begin(), it->second.effects.end(),
                                  [&](const EffectSlot& e) { return e.slotId == sid; });
        if (found != it->second.effects.end()) reordered.push_back(*found);
    }
    // Keep any slots the front end forgot to include (defensive — order
    // messages can race with adds).
    for (const auto& e : it->second.effects) {
        if (std::find_if(reordered.begin(), reordered.end(),
                         [&](const EffectSlot& r) { return r.slotId == e.slotId; })
            == reordered.end()) {
            reordered.push_back(e);
        }
    }
    it->second.effects = std::move(reordered);
    rewireChannelUnlocked(it->second);
    rewireSendSourcesToUnlocked(channelId);
}

void PluginHost::setEffectWetDry(const juce::String& channelId, const juce::String& slotId, float value) {
    value = juce::jlimit(0.0f, 1.0f, value);
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    for (auto& e : it->second.effects) {
        if (e.slotId != slotId) continue;
        e.wetDry = value;
        // Atomic stores on AudioGain — the audio thread picks these up on
        // its next processBlock. No rewire needed; we're only changing gain
        // values, not the graph topology.
        if (e.wetGainNodeId != Graph::NodeID{}) {
            if (auto node = graph.getNodeForId(e.wetGainNodeId))
                if (auto* p = dynamic_cast<AudioGain*>(node->getProcessor()))
                    p->gain.store(value);
        }
        if (e.dryGainNodeId != Graph::NodeID{}) {
            if (auto node = graph.getNodeForId(e.dryGainNodeId))
                if (auto* p = dynamic_cast<AudioGain*>(node->getProcessor()))
                    p->gain.store(1.0f - value);
        }
        return;
    }
}

void PluginHost::bypassEffect(const juce::String& channelId, const juce::String& slotId, bool bypassed) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    for (auto& e : it->second.effects) {
        if (e.slotId == slotId) {
            if (e.bypassed == bypassed) return;
            e.bypassed = bypassed;
            rewireChannelUnlocked(it->second);
            rewireSendSourcesToUnlocked(channelId);
            return;
        }
    }
}

static juce::String effectKey(const juce::String& channelId, const juce::String& slotId) {
    return channelId + "::" + slotId;
}

void PluginHost::showEffectUI(const juce::String& channelId, const juce::String& slotId) {
    juce::MessageManager::callAsync([this, channelId, slotId]() {
        juce::AudioProcessor* proc = nullptr;
        juce::String title;
        {
            std::lock_guard<std::mutex> lock(mutex);
            auto it = channels.find(channelId);
            if (it == channels.end()) return;
            for (const auto& e : it->second.effects) {
                if (e.slotId == slotId) {
                    if (auto node = graph.getNodeForId(e.nodeId)) {
                        proc = node->getProcessor();
                        if (proc) title = proc->getName();
                    }
                    break;
                }
            }
        }
        if (!proc || !proc->hasEditor()) return;

        auto key = effectKey(channelId, slotId);
        auto existing = effectWindows.find(key);
        if (existing != effectWindows.end() && existing->second) {
            existing->second->setVisible(true);
            existing->second->toFront(true);
            return;
        }

        auto* editor = proc->createEditorAndMakeActive();
        if (!editor) return;

        auto win = std::make_unique<PluginWindow>(
            title, editor,
            [this, channelId, slotId]() { hideEffectUI(channelId, slotId); });

#if __APPLE__
        if (auto* peer = win->getPeer()) makeWindowNonActivating(peer->getNativeHandle());
#endif
        effectWindows[key] = std::move(win);
    });
}

void PluginHost::hideEffectUI(const juce::String& channelId, const juce::String& slotId) {
    juce::MessageManager::callAsync([this, channelId, slotId]() {
        effectWindows.erase(effectKey(channelId, slotId));
    });
}

juce::var PluginHost::snapshotEffectStates() {
    std::lock_guard<std::mutex> lock(mutex);
    auto* root = new juce::DynamicObject();
    for (const auto& [chId, slot] : channels) {
        auto* perChannel = new juce::DynamicObject();
        for (const auto& e : slot.effects) {
            auto node = graph.getNodeForId(e.nodeId);
            if (!node || !node->getProcessor()) continue;
            juce::MemoryBlock state;
            node->getProcessor()->getStateInformation(state);
            if (state.getSize() == 0) continue;
            perChannel->setProperty(e.slotId, juce::Base64::toBase64(state.getData(), state.getSize()));
        }
        if (perChannel->getProperties().size() > 0) {
            root->setProperty(chId, juce::var(perChannel));
        } else {
            delete perChannel;
        }
    }
    return juce::var(root);
}

void PluginHost::noteOn(const juce::String& channelId, int pitch, float velocity) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) {
        std::cerr << "[PluginHost] note_on NO CH: " << channelId << std::endl;
        return;
    }
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->collector.addMessageToQueue(
            juce::MidiMessage::noteOn(it->second.midiChannel, pitch, inj->scaleVel(velocity)));
    }
}

void PluginHost::sendProgramChange(const juce::String& channelId, int program, int midiChannel) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) {
        std::cerr << "[PluginHost] program_change NO CH: " << channelId << std::endl;
        return;
    }
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        const int ch = midiChannel > 0 ? midiChannel : it->second.midiChannel;
        const int clampedProgram = program < 0 ? 0 : (program > 127 ? 127 : program);
        inj->collector.addMessageToQueue(
            juce::MidiMessage::programChange(ch, clampedProgram));
        std::cerr << "[PluginHost] program_change ch=" << channelId
                  << " midiCh=" << ch << " program=" << clampedProgram << std::endl;
    }
}

void PluginHost::sendControlChange(const juce::String& channelId, int controller, int value, int midiChannel) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) {
        std::cerr << "[PluginHost] control_change NO CH: " << channelId << std::endl;
        return;
    }
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        const int ch = midiChannel > 0 ? midiChannel : it->second.midiChannel;
        const int clampedCc  = controller < 0 ? 0 : (controller > 127 ? 127 : controller);
        const int clampedVal = value < 0 ? 0 : (value > 127 ? 127 : value);
        inj->collector.addMessageToQueue(
            juce::MidiMessage::controllerEvent(ch, clampedCc, clampedVal));
        std::cerr << "[PluginHost] control_change ch=" << channelId
                  << " midiCh=" << ch << " cc=" << clampedCc << " val=" << clampedVal << std::endl;
    }
}

void PluginHost::setChannelGain(const juce::String& channelId, float gain01) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) {
        std::cerr << "[PluginHost] set_channel_gain NO CH: " << channelId << std::endl;
        return;
    }
    const float clamped = gain01 < 0.0f ? 0.0f : (gain01 > 4.0f ? 4.0f : gain01);
    // Preferred path: write to the channel's audio gain stage so the change
    // applies to actual audio samples. Falls back to the injector's velocity
    // scalar for any legacy slot that predates the gain node — that path is
    // audibly wrong for soundfont instruments, but at least keeps channels
    // that never got upgraded from going fully silent.
    if (it->second.gainNodeId != juce::AudioProcessorGraph::NodeID{}) {
        auto node = graph.getNodeForId(it->second.gainNodeId);
        if (node) {
            if (auto* g = dynamic_cast<AudioGain*>(node->getProcessor())) {
                g->gain.store(clamped, std::memory_order_relaxed);
                std::cerr << "[PluginHost] gain " << channelId << " -> " << clamped << std::endl;
                return;
            }
        }
    }
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->gain.store(clamped, std::memory_order_relaxed);
        std::cerr << "[PluginHost] gain (fallback velocity) " << channelId << " -> " << clamped << std::endl;
    }
}

void PluginHost::noteOff(const juce::String& channelId, int pitch) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->collector.addMessageToQueue(
            juce::MidiMessage::noteOff(it->second.midiChannel, pitch));
    }
}

void PluginHost::allNotesOff(const juce::String& channelId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->collector.addMessageToQueue(
            juce::MidiMessage::allNotesOff(it->second.midiChannel));
        inj->collector.addMessageToQueue(
            juce::MidiMessage::allSoundOff(it->second.midiChannel));
    }
}

void PluginHost::panicAllChannels() {
    std::lock_guard<std::mutex> lock(mutex);
    for (auto& [chId, slot] : channels) {
        auto node = graph.getNodeForId(slot.injectorNodeId);
        if (!node) continue;
        if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
            inj->collector.addMessageToQueue(
                juce::MidiMessage::allNotesOff(slot.midiChannel));
            inj->collector.addMessageToQueue(
                juce::MidiMessage::allSoundOff(slot.midiChannel));
        }
    }
}

void PluginHost::setPatternNote(const juce::String& channelId,
                                const juce::String& noteId,
                                int pitch, float velocity,
                                std::int64_t atSample,
                                std::int64_t durationSamples) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->uiSetNote(noteId, PatternNote{ pitch, velocity, atSample, durationSamples });
    }
}

void PluginHost::clearPatternNote(const juce::String& channelId,
                                  const juce::String& noteId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->uiClearNote(noteId);
    }
}

void PluginHost::clearPattern(const juce::String& channelId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->uiClearAll();
    }
}

// ---- SONG-mode pattern + arrangement API ----
//
// These route into the injector's SONG-mode state (notesByPattern +
// arrangement). Kept separate from setPatternNote/clearPatternNote so
// PAT-mode edits and SONG-mode edits can't accidentally step on each
// other's data.

void PluginHost::setPatternNoteIn(const juce::String& channelId,
                                  const juce::String& patternId,
                                  const juce::String& noteId,
                                  int pitch, float velocity,
                                  std::int64_t atSample,
                                  std::int64_t durationSamples) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->uiSetNoteInPattern(patternId, noteId,
            PatternNote{ pitch, velocity, atSample, durationSamples });
    }
}

void PluginHost::clearPatternNoteIn(const juce::String& channelId,
                                    const juce::String& patternId,
                                    const juce::String& noteId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->uiClearNoteInPattern(patternId, noteId);
    }
}

void PluginHost::clearPatternInChannel(const juce::String& channelId,
                                       const juce::String& patternId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->uiClearPatternInChannel(patternId);
    }
}

void PluginHost::clearAllPatternsIn(const juce::String& channelId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->uiClearAllPatterns();
    }
}

void PluginHost::setChannelArrangement(const juce::String& channelId,
                                       const juce::var& clips) {
    std::vector<ArrangementClip> parsed;
    if (auto* arr = clips.getArray()) {
        parsed.reserve((size_t) arr->size());
        for (const auto& v : *arr) {
            ArrangementClip c{};
            c.patternId              = v["patternId"].toString();
            c.songStartSample        = (std::int64_t) (double) v["songStartSample"];
            c.lengthSamples          = (std::int64_t) (double) v["lengthSamples"];
            c.patternLoopLenSamples  = (std::int64_t) (double) v["patternLoopLenSamples"];
            if (c.patternId.isEmpty()) continue;
            if (c.lengthSamples <= 0 || c.patternLoopLenSamples <= 0) continue;
            parsed.push_back(std::move(c));
        }
    }
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->uiSetArrangement(std::move(parsed));
    }
}

void PluginHost::clearChannelArrangement(const juce::String& channelId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->uiClearArrangement();
    }
}

void PluginHost::showPluginUI(const juce::String& channelId) {
    juce::MessageManager::callAsync([this, channelId]() {
        std::cerr << "[PluginHost] show_plugin_ui for channel=" << channelId << std::endl;
        juce::AudioProcessor* proc = nullptr;
        juce::String title;
        {
            std::lock_guard<std::mutex> lock(mutex);
            auto it = channels.find(channelId);
            if (it == channels.end()) {
                std::cerr << "[PluginHost] channel not found in map" << std::endl;
                return;
            }
            if (auto node = graph.getNodeForId(it->second.pluginNodeId)) {
                proc = node->getProcessor();
                if (proc) title = proc->getName();
            }
        }
        if (!proc) { std::cerr << "[PluginHost] no processor" << std::endl; return; }
        if (!proc->hasEditor()) { std::cerr << "[PluginHost] plugin has no editor" << std::endl; return; }

        // Bring existing window to front if already open.
        auto existing = pluginWindows.find(channelId);
        if (existing != pluginWindows.end() && existing->second) {
            existing->second->setVisible(true);
            existing->second->toFront(true);
            return;
        }

        auto* editor = proc->createEditorAndMakeActive();
        if (!editor) return;

        auto win = std::make_unique<PluginWindow>(
            title, editor,
            [this, channelId]() { hidePluginUI(channelId); });

#if __APPLE__
        // Make the plugin window a floating panel that never becomes key —
        // Nasty keeps keyboard focus while the plugin UI stays visible and
        // clickable. This is what modern DAWs (Bitwig etc.) do for
        // out-of-process plugin hosting.
        if (auto* peer = win->getPeer()) {
            makeWindowNonActivating(peer->getNativeHandle());
        }
#endif

        pluginWindows[channelId] = std::move(win);
    });
}

void PluginHost::hidePluginUI(const juce::String& channelId) {
    juce::MessageManager::callAsync([this, channelId]() {
        pluginWindows.erase(channelId);
    });
}

juce::var PluginHost::listAudioDevices() {
    // Make sure the audio subsystem is initialised — otherwise the current
    // device type is null and we'd return an empty output list. Idempotent.
    if (!audioRunning) startAudio();
    auto* obj = new juce::DynamicObject();
    auto* type = deviceManager.getCurrentDeviceTypeObject();
    juce::StringArray outs;
    if (type) {
        type->scanForDevices();
        outs.addArray(type->getDeviceNames(false));
    }
    if (outs.isEmpty()) {
        for (auto* t : deviceManager.getAvailableDeviceTypes()) {
            if (!t) continue;
            t->scanForDevices();
            outs.addArray(t->getDeviceNames(false));
        }
    }
    // Collapse "DEVICE (N)" variants that JUCE emits for multi-stream devices.
    // We keep the first occurrence for each base name so the dropdown stays
    // clean — the setOutputDevice fallback strips " (N)" as needed when the
    // user picks one.
    juce::StringArray outsClean;
    for (const auto& n : outs) {
        auto base = n.upToLastOccurrenceOf(" (", false, false).trim();
        if (base.isEmpty()) base = n;
        if (!outsClean.contains(base)) outsClean.add(base);
    }
    juce::Array<juce::var> outsVar;
    for (const auto& n : outsClean) outsVar.add(juce::var(n));
    obj->setProperty("outputs", juce::var(outsVar));
    juce::AudioDeviceManager::AudioDeviceSetup setup;
    deviceManager.getAudioDeviceSetup(setup);
    obj->setProperty("currentOutput", juce::var(setup.outputDeviceName));
    if (auto* dev = deviceManager.getCurrentAudioDevice()) {
        obj->setProperty("sampleRate", juce::var(dev->getCurrentSampleRate()));
    }
    return juce::var(obj);
}

juce::var PluginHost::currentOutputSnapshot() const {
    auto* obj = new juce::DynamicObject();
    // Cast away const only for the JUCE getter — the device manager doesn't
    // provide a const accessor, but we only read here.
    auto* dev = const_cast<juce::AudioDeviceManager&>(deviceManager).getCurrentAudioDevice();
    if (dev) {
        obj->setProperty("deviceName",     juce::var(dev->getName()));
        obj->setProperty("sampleRate",     juce::var(dev->getCurrentSampleRate()));
        obj->setProperty("outputChannels", juce::var(dev->getActiveOutputChannels().countNumberOfSetBits()));
    } else {
        obj->setProperty("deviceName",     juce::var(juce::String()));
        obj->setProperty("sampleRate",     juce::var(0.0));
        obj->setProperty("outputChannels", juce::var(0));
    }
    return juce::var(obj);
}

juce::var PluginHost::listAudioInputs() {
    if (!audioRunning) startAudio();
    auto* obj = new juce::DynamicObject();
    juce::StringArray ins;
    for (auto* t : deviceManager.getAvailableDeviceTypes()) {
        if (!t) continue;
        t->scanForDevices();
        ins.addArray(t->getDeviceNames(true /*isInput*/));
    }
    juce::StringArray insClean;
    for (const auto& n : ins) {
        auto base = n.upToLastOccurrenceOf(" (", false, false).trim();
        if (base.isEmpty()) base = n;
        if (!insClean.contains(base)) insClean.add(base);
    }
    juce::Array<juce::var> insVar;
    for (const auto& n : insClean) insVar.add(juce::var(n));
    obj->setProperty("inputs", juce::var(insVar));
    juce::AudioDeviceManager::AudioDeviceSetup setup;
    deviceManager.getAudioDeviceSetup(setup);
    obj->setProperty("currentInput", juce::var(setup.inputDeviceName));
    return juce::var(obj);
}

juce::var PluginHost::currentInputSnapshot() const {
    auto* obj = new juce::DynamicObject();
    juce::AudioDeviceManager::AudioDeviceSetup setup;
    const_cast<juce::AudioDeviceManager&>(deviceManager).getAudioDeviceSetup(setup);
    obj->setProperty("deviceName", juce::var(setup.inputDeviceName));
    auto* dev = const_cast<juce::AudioDeviceManager&>(deviceManager).getCurrentAudioDevice();
    obj->setProperty("inputChannels",
        juce::var(dev ? dev->getActiveInputChannels().countNumberOfSetBits() : 0));
    return juce::var(obj);
}

juce::String PluginHost::setInputDevice(const juce::String& deviceName) {
    if (!audioRunning) startAudio();

    juce::AudioDeviceManager::AudioDeviceSetup setup;
    deviceManager.getAudioDeviceSetup(setup);
    setup.inputDeviceName = deviceName;
    setup.useDefaultInputChannels = deviceName.isNotEmpty();
    if (deviceName.isEmpty()) setup.inputChannels.clear();

    // setAudioDeviceSetup alone doesn't re-negotiate the input side once the
    // device is already running — the device manager's numInputChansNeeded
    // stays 2 but no input channels come through until we go through
    // initialise() again. Re-init keeps output stable because we pass the
    // captured `setup` verbatim, including outputDeviceName.
    deviceManager.removeAudioCallback(this);
    juce::String err = deviceManager.initialise(
        /*numInputs*/ deviceName.isNotEmpty() ? 2 : 0,
        /*numOutputs*/ 2,
        /*savedState*/ nullptr,
        /*selectDefaultDevice*/ true,
        /*preferredDefault*/ juce::String(),
        &setup);
    deviceManager.addAudioCallback(this);
    if (err.isNotEmpty()) {
        std::cerr << "[PluginHost] setInputDevice failed: " << err << std::endl;
        return err;
    }
    if (auto* dev = deviceManager.getCurrentAudioDevice()) {
        std::cerr << "[PluginHost] input device: " << setup.inputDeviceName
                  << " (" << dev->getActiveInputChannels().countNumberOfSetBits()
                  << " input channels active)" << std::endl;
    }
    // Wire any existing audio-input passthroughs (buses with the mic flag) to
    // the freshly-live input node. Bridge already holds MessageManagerLock —
    // don't re-take it here or lockWasGained returns false.
    {
        std::lock_guard<std::mutex> lock(mutex);
        reconnectAudioInputsUnlocked();
    }
    return {};
}

void PluginHost::reconnectAudioInputsUnlocked() {
    auto inNode = graph.getNodeForId(Graph::NodeID(1)); // audioInputNode
    if (!inNode) return;
    auto* inProc = inNode->getProcessor();
    const int numInputCh = inProc ? inProc->getTotalNumOutputChannels() : 0;
    for (auto& kv : channels) {
        auto& slot = kv.second;
        if (!slot.isAudioInput) continue;
        // Remove any stale input-side connections into this passthrough — the
        // input channel count might have changed (mono mic → stereo interface).
        auto conns = graph.getConnections();
        for (const auto& c : conns) {
            if (c.destination.nodeID == slot.pluginNodeId
                && c.source.nodeID == inNode->nodeID) {
                graph.removeConnection(c);
            }
        }
        if (numInputCh <= 0) continue;
        // Left → left, right → right. Mono input: duplicate ch0 to both
        // sides so the mixer feels stereo even with a mono mic.
        graph.addConnection({{inNode->nodeID, 0}, {slot.pluginNodeId, 0}});
        if (numInputCh >= 2) {
            graph.addConnection({{inNode->nodeID, 1}, {slot.pluginNodeId, 1}});
        } else {
            graph.addConnection({{inNode->nodeID, 0}, {slot.pluginNodeId, 1}});
        }
    }
}

juce::String PluginHost::addAudioClip(const juce::String& clipId,
                                      const juce::String& path,
                                      const juce::String& busId,
                                      juce::int64 songStartSample,
                                      juce::int64 lengthSamples) {
    startAudio();

    auto player = std::make_unique<AudioClipPlayer>();
    if (!player->loadFile(path, clipFormatManager)) {
        return "couldn't read WAV: " + path;
    }
    player->setTransport(&transport);
    // PatternPlayer position wraps at loopLength — hand it over so the clip
    // re-fires every loop iteration in both PAT and SONG modes. Without
    // this, the clip's window is only crossed once during Transport's
    // monotonic forward walk and subsequent loops stay silent.
    player->setPatternPlayer(&patternPlayer);
    player->setClipTiming(songStartSample, lengthSamples);

    // Add to graph BEFORE taking the lock — no map mutation yet.
    auto node = graph.addNode(std::move(player));
    if (node == nullptr) return "graph rejected audio-clip node";

    std::lock_guard<std::mutex> lock(mutex);
    // Idempotent: replace any existing clip with the same id.
    auto existing = audioClips.find(clipId);
    if (existing != audioClips.end()) {
        graph.removeNode(existing->second.nodeId);
        audioClips.erase(existing);
    }
    // Wire into the target bus (or master output if the bus doesn't exist).
    auto outNode = graph.getNodeForId(Graph::NodeID(2));
    Graph::NodeID targetNodeId = outNode ? outNode->nodeID : Graph::NodeID{};
    auto busIt = channels.find(busId);
    if (busIt != channels.end()) {
        targetNodeId = busIt->second.pluginNodeId;
    } else {
        // Fall back to master_bus if the named bus isn't the target of a
        // create_bus command yet — matches the rewire behaviour above.
        auto masterIt = channels.find("master_bus");
        if (masterIt != channels.end()) targetNodeId = masterIt->second.pluginNodeId;
    }
    for (int ch = 0; ch < 2; ++ch) {
        graph.addConnection({{node->nodeID, ch}, {targetNodeId, ch}});
    }
    audioClips[clipId] = { node->nodeID, busId };
    std::cerr << "[PluginHost] audio clip added id=" << clipId
              << " bus=" << busId
              << " start=" << songStartSample
              << " len=" << lengthSamples << std::endl;
    return {};
}

void PluginHost::removeAudioClip(const juce::String& clipId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = audioClips.find(clipId);
    if (it == audioClips.end()) return;
    // Zero the clip window first — processBlock bails on length=0, so the
    // very next audio buffer stops emitting even before JUCE's render-
    // sequence rebuild removes the node. Belt-and-braces: suspend the graph
    // around the removal so an in-flight buffer can't dereference a Node
    // whose processor is about to be deleted.
    auto node = graph.getNodeForId(it->second.nodeId);
    if (node) {
        if (auto* p = dynamic_cast<AudioClipPlayer*>(node->getProcessor())) {
            p->setClipTiming(0, 0);
        }
    }
    graph.suspendProcessing(true);
    graph.removeNode(it->second.nodeId);
    graph.suspendProcessing(false);
    audioClips.erase(it);
}

void PluginHost::setAudioClipPosition(const juce::String& clipId,
                                      juce::int64 songStartSample,
                                      juce::int64 lengthSamples) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = audioClips.find(clipId);
    if (it == audioClips.end()) return;
    auto node = graph.getNodeForId(it->second.nodeId);
    if (!node) return;
    if (auto* player = dynamic_cast<AudioClipPlayer*>(node->getProcessor())) {
        player->setClipTiming(songStartSample, lengthSamples);
    }
}

juce::String PluginHost::startRecording(juce::String& outPath) {
    outPath = juce::String();
    if (recordingActive.load(std::memory_order_acquire)) return "already recording";
    auto* dev = deviceManager.getCurrentAudioDevice();
    if (!dev) return "no audio device open";
    const int numInputCh = dev->getActiveInputChannels().countNumberOfSetBits();
    if (numInputCh <= 0) return "no input channels — turn IN on a mixer strip first";
    const double sr = dev->getCurrentSampleRate();

    auto dir = juce::File::getSpecialLocation(juce::File::userMusicDirectory)
                   .getChildFile("Nasty Recordings");
    if (!dir.createDirectory()) {
        // createDirectory returns Result — some builds return bool. If it fails
        // we'll surface the writer-open error below anyway.
    }
    auto ts = juce::Time::getCurrentTime().formatted("%Y%m%d-%H%M%S");
    auto file = dir.getChildFile("mic-" + ts + ".wav");

    juce::WavAudioFormat wav;
    std::unique_ptr<juce::FileOutputStream> stream(file.createOutputStream());
    if (!stream || !stream->openedOk()) {
        return "couldn't open " + file.getFullPathName() + " for writing";
    }
    auto* writer = wav.createWriterFor(stream.get(), sr, (unsigned) numInputCh, 24, {}, 0);
    if (!writer) return "couldn't create WAV writer";
    stream.release(); // writer owns the stream now

    recordingWriter.reset(writer);
    recordingFile = file;
    recordingSamples.store(0, std::memory_order_relaxed);
    recordingActive.store(true, std::memory_order_release);
    outPath = file.getFullPathName();
    std::cerr << "[PluginHost] recording started → " << outPath
              << " sr=" << sr << " ch=" << numInputCh << std::endl;
    return {};
}

juce::String PluginHost::stopRecording(juce::String& outPath, juce::int64& outSamples) {
    if (!recordingActive.load(std::memory_order_acquire)) {
        outPath = juce::String();
        outSamples = 0;
        return "not recording";
    }
    recordingActive.store(false, std::memory_order_release);
    // Give the audio thread one buffer to notice the flag drop before we
    // delete the writer out from under it. In practice writeFromFloatArrays
    // is called synchronously inside the audio callback so the flag check
    // gates it; but a tiny sleep here is cheap belt-and-braces.
    juce::Thread::sleep(20);
    outPath = recordingFile.getFullPathName();
    outSamples = recordingSamples.load(std::memory_order_relaxed);
    recordingWriter.reset(); // flushes + closes the underlying WAV
    std::cerr << "[PluginHost] recording stopped → " << outPath
              << " (" << outSamples << " samples)" << std::endl;
    return {};
}

void PluginHost::setChannelAudioInput(const juce::String& channelId, bool enabled) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    if (it->second.isAudioInput == enabled) return;
    it->second.isAudioInput = enabled;
    if (!enabled) {
        // Remove any existing audioInputNode → this bus/channel connections.
        auto inNode = graph.getNodeForId(Graph::NodeID(1));
        if (inNode) {
            auto conns = graph.getConnections();
            for (const auto& c : conns) {
                if (c.destination.nodeID == it->second.pluginNodeId
                    && c.source.nodeID == inNode->nodeID) {
                    graph.removeConnection(c);
                }
            }
        }
    } else {
        reconnectAudioInputsUnlocked();
    }
}

juce::String PluginHost::createAudioInputChannel(const juce::String& channelId) {
    startAudio();
    auto node     = graph.addNode(std::make_unique<BusPassthrough>());
    auto gainNode = addGainNode();
    if (node == nullptr || gainNode == nullptr) {
        if (node)     graph.removeNode(node->nodeID);
        if (gainNode) graph.removeNode(gainNode->nodeID);
        return juce::String("graph rejected audio-input passthrough");
    }

    std::lock_guard<std::mutex> lock(mutex);
    // Replace existing channel with same id (idempotent create).
    auto existing = channels.find(channelId);
    if (existing != channels.end()) {
        for (const auto& e : existing->second.effects) graph.removeNode(e.nodeId);
        graph.removeNode(existing->second.pluginNodeId);
        if (existing->second.injectorNodeId != juce::AudioProcessorGraph::NodeID{})
            graph.removeNode(existing->second.injectorNodeId);
        if (existing->second.gainNodeId != juce::AudioProcessorGraph::NodeID{})
            graph.removeNode(existing->second.gainNodeId);
        channels.erase(existing);
    }
    ChannelSlot slot{
        node->nodeID,                          // pluginNodeId = passthrough
        juce::AudioProcessorGraph::NodeID{},   // no MIDI injector
        gainNode->nodeID,                      // gain at tail
        1,                                     // midiChannel unused
        {},                                    // no effects yet
        {},                                    // routes to master by default
        false,                                 // isBus
        true                                   // isAudioInput
    };
    channels[channelId] = slot;
    rewireChannelUnlocked(channels[channelId]);
    // Wire the graph audio input node into this passthrough so signal actually
    // flows. Safe to call every time — reconnect prunes stale wires first.
    reconnectAudioInputsUnlocked();
    return {};
}

juce::String PluginHost::setOutputDevice(const juce::String& deviceName) {
    if (!audioRunning) startAudio();
    juce::AudioDeviceManager::AudioDeviceSetup setup;
    deviceManager.getAudioDeviceSetup(setup);
    setup.outputDeviceName = deviceName;
    setup.useDefaultOutputChannels = true;
    auto err = deviceManager.setAudioDeviceSetup(setup, true);
    // JUCE sometimes appends " (N)" to distinguish devices with the same
    // base name across HAL / IOAudio types. If the user picks the numbered
    // one but CoreAudio only knows the plain name (or vice-versa), fall back
    // to the stripped form once before giving up.
    if (err.isNotEmpty()) {
        juce::String stripped = deviceName.upToLastOccurrenceOf(" (", false, false).trim();
        if (stripped.isNotEmpty() && stripped != deviceName) {
            std::cerr << "[PluginHost] setOutputDevice retry with stripped name: '"
                      << stripped << "'" << std::endl;
            setup.outputDeviceName = stripped;
            err = deviceManager.setAudioDeviceSetup(setup, true);
        }
    }
    if (err.isEmpty()) {
        if (auto* dev = deviceManager.getCurrentAudioDevice()) {
            std::cerr << "[PluginHost] switched output to: " << dev->getName() << std::endl;
        }
        // Input side may have been renegotiated (same device now for both) —
        // re-establish audio-input passthrough wiring so bus mic feeds
        // survive an output switch.
        std::lock_guard<std::mutex> lock(mutex);
        reconnectAudioInputsUnlocked();
    } else {
        std::cerr << "[PluginHost] setOutputDevice failed: " << err << std::endl;
    }
    return err;
}

juce::var PluginHost::snapshotPluginStates() {
    std::lock_guard<std::mutex> lock(mutex);
    auto* obj = new juce::DynamicObject();
    for (const auto& [chId, slot] : channels) {
        auto node = graph.getNodeForId(slot.pluginNodeId);
        if (!node || !node->getProcessor()) continue;
        juce::MemoryBlock state;
        node->getProcessor()->getStateInformation(state);
        if (state.getSize() == 0) continue;
        obj->setProperty(chId, juce::Base64::toBase64(state.getData(), state.getSize()));
    }
    return juce::var(obj);
}

void PluginHost::hideAllPluginUIs() {
    juce::MessageManager::callAsync([this]() {
        for (auto& kv : pluginWindows) {
            if (kv.second) kv.second->setVisible(false);
        }
    });
}

void PluginHost::setPluginWindowsFloating(bool floating) {
    juce::MessageManager::callAsync([this, floating]() {
#if __APPLE__
        // If Nasty said "I lost focus" but we (engine) are the ones who took
        // focus (user clicked a plugin's dialog, file picker, etc.), don't
        // lower plugin windows — otherwise they flicker off and on as user
        // interacts with the dialog. Only actually lower when a truly
        // different app (Chrome, Slack) is taking over.
        if (!floating && isEngineAppActive()) return;

        for (auto& kv : pluginWindows) {
            if (!kv.second) continue;
            if (auto* peer = kv.second->getPeer()) {
                setWindowFloating(peer->getNativeHandle(), floating);
            }
        }
#else
        (void) floating;
#endif
    });
}

void PluginHost::setParam(const juce::String& channelId,
                          const juce::String& slotId,
                          int paramIndex, float value01) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    juce::AudioProcessorGraph::NodeID nodeId;
    if (slotId.isEmpty()) {
        nodeId = it->second.pluginNodeId;
    } else {
        for (const auto& e : it->second.effects) {
            if (e.slotId == slotId) { nodeId = e.nodeId; break; }
        }
    }
    if (auto node = graph.getNodeForId(nodeId)) {
        auto& params = node->getProcessor()->getParameters();
        if (paramIndex >= 0 && paramIndex < params.size()) {
            params[paramIndex]->setValueNotifyingHost(value01);
        }
    }
}

juce::var PluginHost::paramsForOwner(const juce::String& channelId,
                                     const juce::String& slotId) const {
    juce::Array<juce::var> arr;
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return juce::var(arr);
    juce::AudioProcessorGraph::NodeID nodeId;
    if (slotId.isEmpty()) {
        nodeId = it->second.pluginNodeId;
    } else {
        for (const auto& e : it->second.effects) {
            if (e.slotId == slotId) { nodeId = e.nodeId; break; }
        }
    }
    // graph.getNodeForId is not marked const in JUCE, but reading a node's
    // param list is safe — bounce through a const_cast.
    if (auto node = const_cast<juce::AudioProcessorGraph&>(graph).getNodeForId(nodeId)) {
        auto& params = node->getProcessor()->getParameters();
        for (int i = 0; i < params.size(); ++i) {
            auto* p = params[i];
            auto* o = new juce::DynamicObject();
            o->setProperty("index", i);
            o->setProperty("name", p->getName(48));
            o->setProperty("value", p->getValue());
            arr.add(juce::var(o));
        }
    }
    return juce::var(arr);
}

} // namespace nasty
