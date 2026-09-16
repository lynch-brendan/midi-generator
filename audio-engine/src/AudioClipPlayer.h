#pragma once

// AudioClipPlayer — a JUCE AudioProcessor that streams one recorded WAV back
// during SONG-mode transport playback. Positioned playback: reads the shared
// Transport's current sample and only emits audio when the clip window
// overlaps the current buffer. Meant for mic takes captured by Phase 2 that
// need to play back through the same mixer bus they were recorded on.

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include <atomic>
#include "Transport.h"

namespace nasty {

class AudioClipPlayer : public juce::AudioProcessor {
public:
    AudioClipPlayer();
    ~AudioClipPlayer() override = default;

    // Load a WAV/AIFF into memory. Small takes (seconds/minutes) fit fine;
    // streaming from disk is a future win once takes get long enough to
    // strain RAM. Returns true on success.
    bool loadFile(const juce::String& path, juce::AudioFormatManager& fmt);

    // Position the clip on the session timeline. Both are in session samples
    // (Transport-relative). Audio-thread-safe: atomic stores, no lock.
    void setClipTiming(juce::int64 songStartSample, juce::int64 lengthSamples);

    void setTransport(const Transport* t) noexcept { transport = t; }

    const juce::String getName() const override    { return "NastyAudioClip"; }
    void prepareToPlay(double, int) override        {}
    void releaseResources() override                {}
    bool acceptsMidi() const override               { return false; }
    bool producesMidi() const override              { return false; }
    double getTailLengthSeconds() const override    { return 0.0; }

    void processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer& midi) override;
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
    juce::AudioBuffer<float> sampleBuffer;
    std::atomic<juce::int64> clipStart{0};
    std::atomic<juce::int64> clipLength{0};
    const Transport* transport = nullptr;
};

} // namespace nasty
