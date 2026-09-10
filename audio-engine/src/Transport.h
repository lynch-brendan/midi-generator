#pragma once

// Transport — the engine's single source of truth for time.
//
// One monotonic sample counter, advanced by the audio callback exactly once
// per buffer. Everything else — playhead visual, pattern playback, recording
// timestamps, tempo-sync for plugins — is a lookup off this counter.
//
// Threading:
//   * Audio thread: beginBuffer()/endBuffer() bracket each callback. Between
//     them, getBufferStartSample()/getBufferSize() report where in the
//     timeline this buffer sits. endBuffer() advances the master counter iff
//     playing, so stop() naturally freezes position without racy stop logic.
//   * Any thread: getCurrentSample()/getIsPlaying()/getTempoBpm() read the
//     latest atomic values. UI reads these every frame to draw the playhead.
//   * UI thread: play()/stop()/seek()/setTempo()/setLoopLengthSamples() are
//     the write API. All writes are single-word atomic stores.
//
// The counter monotonically increases while playing — it does NOT wrap at
// loop end. Loop position is a lookup: `currentSample % loopLengthSamples`.
// A monotonic clock keeps recording, tempo sync, and long-form arrangements
// working the same as short loops.

#include <atomic>
#include <cstdint>

namespace nasty {

class Transport {
public:
    // PAT: MidiInjector walks the loop-wrapped PatternPlayer position and
    // fires the flat `patternNotes` for each channel. SONG: it walks the
    // monotonic Transport clock against the per-channel arrangement (clips
    // reference patterns; patterns tile inside each clip to fill its length).
    enum class Mode : int { PAT = 0, SONG = 1 };

    // ---- AUDIO THREAD ONLY (between callback in and out) ----
    void beginBuffer(int numSamples) noexcept {
        bufferStartSample = currentSample.load(std::memory_order_acquire);
        bufferSizeSamples = numSamples;
    }
    void endBuffer() noexcept {
        if (isPlaying.load(std::memory_order_relaxed)) {
            currentSample.store(bufferStartSample + bufferSizeSamples,
                                std::memory_order_release);
        }
    }
    std::int64_t getBufferStartSample() const noexcept { return bufferStartSample; }
    int          getBufferSize()        const noexcept { return bufferSizeSamples; }

    // ---- ANY THREAD READERS ----
    std::int64_t getCurrentSample()      const noexcept { return currentSample.load(std::memory_order_acquire); }
    bool         getIsPlaying()          const noexcept { return isPlaying.load(std::memory_order_acquire); }
    double       getTempoBpm()           const noexcept { return tempoBpm.load(std::memory_order_acquire); }
    std::int64_t getLoopLengthSamples()  const noexcept { return loopLengthSamples.load(std::memory_order_acquire); }
    double       getSampleRate()         const noexcept { return sampleRate.load(std::memory_order_acquire); }
    Mode         getMode()               const noexcept { return static_cast<Mode>(mode.load(std::memory_order_acquire)); }

    // ---- UI THREAD WRITERS ----
    void play()                                noexcept { isPlaying.store(true,  std::memory_order_release); }
    void stop()                                noexcept { isPlaying.store(false, std::memory_order_release); }
    void seek(std::int64_t s)                  noexcept { currentSample.store(s, std::memory_order_release); }
    void setTempo(double bpm)                  noexcept { tempoBpm.store(bpm,    std::memory_order_release); }
    void setLoopLengthSamples(std::int64_t s)  noexcept { loopLengthSamples.store(s, std::memory_order_release); }
    void setSampleRate(double sr)              noexcept { sampleRate.store(sr,   std::memory_order_release); }
    void setMode(Mode m)                       noexcept { mode.store(static_cast<int>(m), std::memory_order_release); }

private:
    std::atomic<std::int64_t> currentSample{0};
    std::atomic<bool>         isPlaying{false};
    std::atomic<double>       tempoBpm{120.0};
    std::atomic<std::int64_t> loopLengthSamples{0};
    std::atomic<double>       sampleRate{48000.0};
    std::atomic<int>          mode{static_cast<int>(Mode::PAT)};

    // Audio-thread scratch, only touched between beginBuffer/endBuffer.
    std::int64_t bufferStartSample{0};
    int          bufferSizeSamples{0};
};

} // namespace nasty
