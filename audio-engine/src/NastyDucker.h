#pragma once

// NastyDucker — a native sidechain compressor. Built into the engine so
// sidechain always works out of the box, without depending on which third-
// party plugins the user happens to have installed. Two input buses are
// declared: main audio (bus 0, stereo) and sidechain trigger (bus 1, stereo),
// both enabled by default. The rewire path connects the source strip's
// gain output into channels 2/3 (the sidechain bus) so the sidechain input
// carries the trigger signal (e.g. kick), while the main audio flows through
// channels 0/1 as usual.

#include <juce_audio_processors/juce_audio_processors.h>
#include <atomic>

namespace nasty {

class NastyDucker : public juce::AudioProcessor {
public:
    NastyDucker();
    ~NastyDucker() override = default;

    const juce::String getName() const override    { return "NastyDucker"; }
    void prepareToPlay(double sampleRate, int blockSize) override;
    void releaseResources() override               {}
    bool acceptsMidi() const override              { return false; }
    bool producesMidi() const override             { return false; }
    double getTailLengthSeconds() const override   { return 0.0; }

    // Allow both the main and sidechain buses to negotiate to stereo. Without
    // this the plugin might come up with sidechain disabled (0 channels) and
    // our detection logic (>=4 total input channels) would skip it.
    bool isBusesLayoutSupported(const BusesLayout& layouts) const override;

    void processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer& midi) override;
    using AudioProcessor::processBlock;

    juce::AudioProcessorEditor* createEditor() override    { return nullptr; }
    bool hasEditor() const override                        { return false; }

    // Simple parameter model: threshold (dB, -60..0), ratio (1..20),
    // attack (ms, 0.5..100), release (ms, 5..1000), makeup (dB, 0..24).
    // Exposed through the AudioProcessorParameter interface so the existing
    // set_param / paramsForOwner pipeline can twist them from the UI or AI.
    int getNumPrograms() override                          { return 1; }
    int getCurrentProgram() override                       { return 0; }
    void setCurrentProgram(int) override                   {}
    const juce::String getProgramName(int) override        { return "Default"; }
    void changeProgramName(int, const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override;
    void setStateInformation(const void*, int) override;

private:
    // Parameters. Values stored 0..1 in AudioParameterFloat land, converted
    // to real ranges inside processBlock.
    juce::AudioParameterFloat* threshold = nullptr; // -60..0 dB
    juce::AudioParameterFloat* ratio     = nullptr; // 1..20
    juce::AudioParameterFloat* attackMs  = nullptr; // 0.5..100 ms
    juce::AudioParameterFloat* releaseMs = nullptr; // 5..1000 ms
    juce::AudioParameterFloat* makeupDb  = nullptr; // 0..24 dB

    // Envelope state — smoothed gain-reduction expressed in linear amplitude.
    // Updated per sample from the sidechain input's RMS-ish level.
    float envelope = 1.0f;
    double sampleRate = 48000.0;
};

} // namespace nasty
