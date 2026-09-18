#include "AudioClipPlayer.h"

namespace nasty {

AudioClipPlayer::AudioClipPlayer()
    : juce::AudioProcessor(BusesProperties()
        .withOutput("Out", juce::AudioChannelSet::stereo(), true)) {}

bool AudioClipPlayer::loadFile(const juce::String& path,
                               juce::AudioFormatManager& fmt) {
    juce::File f(path);
    if (!f.existsAsFile()) return false;
    std::unique_ptr<juce::AudioFormatReader> reader(fmt.createReaderFor(f));
    if (!reader) return false;
    const int chs = (int) reader->numChannels;
    const int len = (int) reader->lengthInSamples;
    if (chs <= 0 || len <= 0) return false;
    sampleBuffer.setSize(chs, len, false, true, false);
    reader->read(&sampleBuffer, 0, len, 0, true, true);
    return true;
}

void AudioClipPlayer::setClipTiming(juce::int64 songStartSample,
                                    juce::int64 lengthSamples) {
    clipStart.store(songStartSample, std::memory_order_relaxed);
    clipLength.store(lengthSamples, std::memory_order_relaxed);
}

void AudioClipPlayer::processBlock(juce::AudioBuffer<float>& buf,
                                   juce::MidiBuffer&) {
    buf.clear();
    if (transport == nullptr || sampleBuffer.getNumSamples() == 0) return;
    if (!transport->getIsPlaying()) return;
    // Skip during count-in — Transport reports a negative buffer start until
    // the count-in resolves. Without this the clip would fire on tick 0
    // before the metronome finishes counting in.
    if (transport->getBufferStartSample() < 0) return;

    // Prefer PatternPlayer's wrapped position when it's wired — it wraps at
    // the loop boundary so the clip re-fires every loop iteration. Fall
    // back to Transport's monotonic sample for legacy setups without a
    // PatternPlayer (single-shot playback until source end).
    const juce::int64 bufStart = (patternPlayer != nullptr)
        ? patternPlayer->getBufferStartPosition()
        : transport->getCurrentSample();
    const int numSamples = buf.getNumSamples();
    const juce::int64 cs = clipStart.load(std::memory_order_relaxed);
    const juce::int64 cl = clipLength.load(std::memory_order_relaxed);
    const juce::int64 clipEnd = cs + cl;

    // Clip window doesn't touch this buffer — bail cheaply.
    if (bufStart + numSamples <= cs) return;
    if (bufStart >= clipEnd) return;

    // Overlap window in buffer coordinates.
    const juce::int64 startInBuf = juce::jmax((juce::int64) 0, cs - bufStart);
    const juce::int64 endInBuf   = juce::jmin((juce::int64) numSamples, clipEnd - bufStart);
    const juce::int64 samplesToPlay = endInBuf - startInBuf;
    if (samplesToPlay <= 0) return;

    // Where to read from in the source WAV.
    const juce::int64 srcOffset = bufStart + startInBuf - cs;
    const juce::int64 srcAvail  = juce::jmin(samplesToPlay,
        (juce::int64) sampleBuffer.getNumSamples() - srcOffset);
    if (srcAvail <= 0) return;

    const int outChs = buf.getNumChannels();
    const int inChs  = sampleBuffer.getNumChannels();
    for (int c = 0; c < outChs; ++c) {
        const int srcCh = juce::jmin(c, inChs - 1);
        buf.copyFrom(c, (int) startInBuf,
                     sampleBuffer, srcCh, (int) srcOffset, (int) srcAvail);
    }
}

} // namespace nasty
