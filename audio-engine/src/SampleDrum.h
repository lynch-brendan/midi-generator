#pragma once

// SampleDrum — a JUCE AudioProcessor that plays ONE drum sample and
// pitch-shifts it based on the incoming MIDI note. Meant for FL-style drum
// channels: one channel = one sample (kick.wav / snare.wav / etc.), and
// drawing a higher/lower note in the piano roll shifts the sample's pitch.

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_audio_formats/juce_audio_formats.h>

namespace nasty {

class SampleDrum : public juce::AudioProcessor {
public:
    SampleDrum();
    ~SampleDrum() override = default;

    // Load a WAV/AIFF and set which MIDI note maps to the sample's natural
    // pitch. Notes above/below that shift the playback rate accordingly.
    bool loadSample(const juce::String& path, int rootNote);

    const juce::String getName() const override    { return "NastyDrum"; }
    void prepareToPlay(double sampleRate, int blockSize) override;
    void releaseResources() override               {}
    bool acceptsMidi() const override              { return true; }
    bool producesMidi() const override             { return false; }
    bool isMidiEffect() const override             { return false; }
    double getTailLengthSeconds() const override   { return 1.0; }

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
    juce::AudioFormatManager formatManager;
    juce::Synthesiser synth;
};

} // namespace nasty
