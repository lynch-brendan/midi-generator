#pragma once

// Metronome — engine-hosted click generator, sample-accurate against the
// Transport. Because it lives inside the audio callback and reads the same
// sample counter as the pattern walker, its clicks can NEVER drift from the
// notes being played (the exact bug that killed WebAudio-scheduled clicks:
// two clocks). No IPC latency, no scheduling ahead, no cancel-and-reschedule.
//
// Sound design: short sine burst with a fast exponential decay. Accent beat
// (downbeat) is a semitone higher and slightly louder. Kept deliberately
// simple; the whole render is a few lines in processBlock.

#include <juce_audio_processors/juce_audio_processors.h>
#include "Transport.h"

#include <atomic>
#include <cmath>
#include <cstdint>
#include <vector>

namespace nasty {

class Metronome : public juce::AudioProcessor {
public:
    explicit Metronome(const Transport& t)
        : juce::AudioProcessor(BusesProperties()
              .withOutput("Output", juce::AudioChannelSet::stereo(), true)),
          transport(t) {}

    // Public, thread-safe on/off. UI writes, audio thread reads.
    void setEnabled(bool v) noexcept { enabled.store(v, std::memory_order_release); }
    bool getEnabled() const noexcept { return enabled.load(std::memory_order_acquire); }

    const juce::String getName() const override    { return "NastyMetronome"; }
    void prepareToPlay(double, int) override        {}
    void releaseResources() override                {}
    bool acceptsMidi() const override               { return false; }
    bool producesMidi() const override              { return false; }
    double getTailLengthSeconds() const override    { return 0.06; }

    void processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer&) override {
        buf.clear();
        if (!enabled.load(std::memory_order_acquire)) return;
        if (!transport.getIsPlaying())                return;

        const double sr = transport.getSampleRate();
        if (sr <= 0.0) return;
        const double bpm = transport.getTempoBpm();
        if (bpm <= 0.0) return;

        const std::int64_t samplesPerBeat = (std::int64_t) (60.0 / bpm * sr);
        if (samplesPerBeat <= 0) return;

        const std::int64_t bufferStart = transport.getBufferStartSample();
        const int          numSamples  = buf.getNumSamples();
        const std::int64_t bufferEnd   = bufferStart + numSamples;

        // Trigger a fresh click at every beat boundary that falls inside the
        // buffer window. Multiple beats can trigger in a single buffer if the
        // buffer is large relative to the beat length; the active-voice list
        // handles overlap.
        //
        // Ceiling-to-multiple works for negative bufferStart too (used for
        // count-in: transport seeks to a negative sample so metronome clicks
        // fire before beat 0 without the pattern walker injecting notes).
        // C++ signed integer division truncates toward zero, so we normalise
        // the modulus to always be in [0, samplesPerBeat) before rounding up.
        std::int64_t rem = ((bufferStart % samplesPerBeat) + samplesPerBeat) % samplesPerBeat;
        const std::int64_t firstBeat = (rem == 0)
            ? bufferStart
            : (bufferStart + (samplesPerBeat - rem));
        for (std::int64_t beatSample = firstBeat;
             beatSample < bufferEnd;
             beatSample += samplesPerBeat) {
            if (beatSample < bufferStart) continue;
            // Signed modulo to keep accents on beat 1 for both positive and
            // negative beat indices (count-in vs playback).
            const std::int64_t beatIdx = beatSample / samplesPerBeat;
            std::int64_t accentIdx = beatIdx % 4;
            if (accentIdx < 0) accentIdx += 4;
            const bool accent = (accentIdx == 0);
            voices.push_back({ beatSample, accent ? 2400.0 : 1600.0,
                               accent ? 0.28f : 0.18f });
        }

        // Render every active voice into the buffer. Voices whose 50ms tail
        // has fully elapsed are removed.
        constexpr double clickDurSec = 0.05;
        const int numCh = buf.getNumChannels();
        for (auto it = voices.begin(); it != voices.end(); ) {
            const auto& v = *it;
            const std::int64_t endSample =
                v.startSample + (std::int64_t) (clickDurSec * sr) + 1;
            for (int i = 0; i < numSamples; ++i) {
                const std::int64_t abs = bufferStart + i;
                if (abs < v.startSample) continue;
                if (abs >= endSample)    break;
                const double dt = (double) (abs - v.startSample) / sr;
                const float env = v.amp * (float) std::exp(-dt * 60.0);
                const float s   = env * (float) std::sin(2.0 * M_PI * v.freq * dt);
                for (int c = 0; c < numCh; ++c) buf.addSample(c, i, s);
            }
            if (bufferEnd >= endSample) it = voices.erase(it);
            else                        ++it;
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

private:
    struct Voice {
        std::int64_t startSample;
        double       freq;
        float        amp;
    };
    const Transport& transport;
    std::atomic<bool> enabled{false};
    // Audio-thread only. Tiny vector; overlap in a metronome is essentially
    // never more than 1-2 voices at a time.
    std::vector<Voice> voices;
};

} // namespace nasty
