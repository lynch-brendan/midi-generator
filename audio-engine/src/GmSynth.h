#pragma once

// GmSynth — a General MIDI synth as a JUCE AudioProcessor. Backed by
// FluidSynth + a bundled SoundFont so every channel using it can pick any
// of the 128 GM patches (piano, strings, brass, drums, etc.) with no
// external plugin required.

#include <juce_audio_processors/juce_audio_processors.h>
#include <atomic>
#include <mutex>
#include <fluidsynth.h>

namespace nasty {

class GmSynth : public juce::AudioProcessor {
public:
    GmSynth();
    ~GmSynth() override;

    // Load a SoundFont file. Safe to call once per instance at construction.
    bool loadSoundFont(const juce::String& sf2Path);

    // Set the current GM program (0-127). Channel 10 (index 9) is drums.
    void setProgram(int programNumber);

    // AudioProcessor overrides.
    const juce::String getName() const override    { return "NastyGmSynth"; }
    void prepareToPlay(double sampleRate, int blockSize) override;
    void releaseResources() override               {}
    bool acceptsMidi() const override              { return true; }
    bool producesMidi() const override             { return false; }
    bool isMidiEffect() const override             { return false; }
    double getTailLengthSeconds() const override   { return 2.0; }

    void processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer& midi) override;
    using AudioProcessor::processBlock;

    juce::AudioProcessorEditor* createEditor() override    { return nullptr; }
    bool hasEditor() const override                        { return false; }
    int getNumPrograms() override                          { return 128; }
    int getCurrentProgram() override                       { return currentProgram; }
    void setCurrentProgram(int index) override             { setProgram(index); }
    const juce::String getProgramName(int) override        { return {}; }
    void changeProgramName(int, const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override  {}
    void setStateInformation(const void*, int) override    {}

private:
    fluid_settings_t* settings = nullptr;
    fluid_synth_t*    synth    = nullptr;
    int   sfFontId       = -1;
    int   currentProgram = 0;
    bool  isDrumChannel  = false;
    double curSampleRate = 44100.0;
    std::mutex mutex;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(GmSynth)
};

} // namespace nasty
