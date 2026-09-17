#include "NastyDucker.h"
#include <cmath>

namespace nasty {

static float dbToLin(float db) { return std::pow(10.0f, db * 0.05f); }

NastyDucker::NastyDucker()
    : juce::AudioProcessor(BusesProperties()
        .withInput("Main",      juce::AudioChannelSet::stereo(), true)
        .withInput("Sidechain", juce::AudioChannelSet::stereo(), true)
        .withOutput("Out",      juce::AudioChannelSet::stereo(), true)) {
    addParameter(threshold = new juce::AudioParameterFloat({"threshold", 1}, "Threshold", -60.0f, 0.0f, -18.0f));
    addParameter(ratio     = new juce::AudioParameterFloat({"ratio", 1},     "Ratio",       1.0f, 20.0f,  4.0f));
    addParameter(attackMs  = new juce::AudioParameterFloat({"attack", 1},    "Attack (ms)", 0.5f, 100.0f, 5.0f));
    addParameter(releaseMs = new juce::AudioParameterFloat({"release", 1},   "Release (ms)",5.0f, 1000.0f, 120.0f));
    addParameter(makeupDb  = new juce::AudioParameterFloat({"makeup", 1},    "Makeup (dB)", 0.0f, 24.0f,  0.0f));
}

bool NastyDucker::isBusesLayoutSupported(const BusesLayout& layouts) const {
    // Accept any layout where main + sidechain are both stereo or mono, and
    // the output matches main. This lets the host negotiate freely while
    // still ensuring sidechain shows up as an active bus (my rewire counts
    // total input channels, so we need SC enabled here to hit 4).
    const auto& mainIn = layouts.getChannelSet(true, 0);
    if (mainIn.isDisabled()) return false;
    if (mainIn != juce::AudioChannelSet::stereo()
        && mainIn != juce::AudioChannelSet::mono()) return false;
    if (layouts.getChannelSet(false, 0) != mainIn) return false;
    if (layouts.inputBuses.size() > 1) {
        const auto& sc = layouts.getChannelSet(true, 1);
        // Sidechain may negotiate to stereo or mono; both are fine. Disabled
        // is fine too — some hosts don't wire sidechain and we should still
        // load (we just won't duck in that case).
        if (!sc.isDisabled()
            && sc != juce::AudioChannelSet::stereo()
            && sc != juce::AudioChannelSet::mono()) return false;
    }
    return true;
}

void NastyDucker::prepareToPlay(double sr, int /*blockSize*/) {
    sampleRate = sr > 0.0 ? sr : 48000.0;
    envelope = 1.0f;
}

void NastyDucker::processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer&) {
    // Read parameters once per block. Fine granularity if the user is
    // twisting knobs — 512 samples ≈ 10 ms at 48 kHz, imperceptible.
    const float thrLin  = dbToLin((float) *threshold);
    const float rat     = (float) *ratio;
    const float attCoef = std::exp(-1.0f / (float) (sampleRate * (*attackMs)  * 0.001));
    const float relCoef = std::exp(-1.0f / (float) (sampleRate * (*releaseMs) * 0.001));
    const float makeup  = dbToLin((float) *makeupDb);

    auto mainBus = getBusBuffer(buf, true,  0);
    auto outBus  = getBusBuffer(buf, false, 0);
    const int n = buf.getNumSamples();
    const int mainChs = juce::jmin(mainBus.getNumChannels(), outBus.getNumChannels());

    // Fallback source for the ducking signal — if there IS a sidechain bus
    // connected, prefer it; if not, use the main signal itself (behaves like
    // a normal compressor).
    juce::AudioBuffer<float> scBus;
    const bool haveSc = (getBusCount(true) > 1) && (getBus(true, 1)->isEnabled());
    if (haveSc) scBus = getBusBuffer(buf, true, 1);

    for (int i = 0; i < n; ++i) {
        // Peak-detect across whichever channels feed the sidechain.
        float scPeak = 0.0f;
        if (haveSc && scBus.getNumChannels() > 0) {
            for (int c = 0; c < scBus.getNumChannels(); ++c) {
                scPeak = juce::jmax(scPeak, std::abs(scBus.getReadPointer(c)[i]));
            }
        } else {
            for (int c = 0; c < mainChs; ++c) {
                scPeak = juce::jmax(scPeak, std::abs(mainBus.getReadPointer(c)[i]));
            }
        }
        // Compute gain reduction based on how far above threshold we are.
        float target = 1.0f;
        if (scPeak > thrLin && rat > 1.0f) {
            const float overDb = 20.0f * std::log10(scPeak / thrLin);
            const float grDb   = overDb - overDb / rat;
            target = dbToLin(-grDb);
        }
        // Attack / release smoothing on the reduction envelope.
        const float coef = (target < envelope) ? attCoef : relCoef;
        envelope = target + (envelope - target) * coef;
        const float g = envelope * makeup;
        // Apply gain reduction to every main channel, write to output.
        for (int c = 0; c < mainChs; ++c) {
            outBus.getWritePointer(c)[i] = mainBus.getReadPointer(c)[i] * g;
        }
    }
}

void NastyDucker::getStateInformation(juce::MemoryBlock& out) {
    juce::MemoryOutputStream stream(out, false);
    stream.writeFloat(*threshold);
    stream.writeFloat(*ratio);
    stream.writeFloat(*attackMs);
    stream.writeFloat(*releaseMs);
    stream.writeFloat(*makeupDb);
}

void NastyDucker::setStateInformation(const void* data, int size) {
    juce::MemoryInputStream stream(data, (size_t) size, false);
    if (stream.getNumBytesRemaining() < 20) return;
    *threshold = stream.readFloat();
    *ratio     = stream.readFloat();
    *attackMs  = stream.readFloat();
    *releaseMs = stream.readFloat();
    *makeupDb  = stream.readFloat();
}

} // namespace nasty
