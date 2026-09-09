#include "SampleDrum.h"
#include <iostream>

namespace nasty {

SampleDrum::SampleDrum()
    : juce::AudioProcessor(BusesProperties()
        .withOutput("Output", juce::AudioChannelSet::stereo(), true)) {
    formatManager.registerBasicFormats();
    // 4 voices — enough for rapid retriggers (roll fills) without eating CPU.
    for (int i = 0; i < 4; ++i)
        synth.addVoice(new juce::SamplerVoice());
}

bool SampleDrum::loadSample(const juce::String& path, int rootNote) {
    juce::File f(path);
    if (!f.existsAsFile()) {
        std::cerr << "[SampleDrum] sample missing: " << path << std::endl;
        return false;
    }
    std::unique_ptr<juce::AudioFormatReader> reader(formatManager.createReaderFor(f));
    if (!reader) {
        std::cerr << "[SampleDrum] no reader for: " << path << std::endl;
        return false;
    }
    juce::BigInteger allNotes;
    allNotes.setRange(0, 128, true);
    synth.clearSounds();
    // Max sample length 15s — plenty for a drum hit, keeps memory bounded.
    synth.addSound(new juce::SamplerSound(
        "drum", *reader, allNotes,
        /*rootMidiNote*/ rootNote,
        /*attack*/ 0.0, /*release*/ 0.1,
        /*maxSampleLengthSeconds*/ 15.0));
    return true;
}

void SampleDrum::prepareToPlay(double sampleRate, int /*blockSize*/) {
    synth.setCurrentPlaybackSampleRate(sampleRate);
}

void SampleDrum::processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer& midi) {
    buf.clear();
    synth.renderNextBlock(buf, midi, 0, buf.getNumSamples());
}

} // namespace nasty
