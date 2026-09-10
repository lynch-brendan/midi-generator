#pragma once

// PatternPlayer — the loop-state layer that sits on top of the monotonic
// Transport. This is where the "professional DAW" architecture lives.
//
// Transport is monotonic session time — it never wraps, it never changes
// direction. Metronome runs off it. Anything that needs to answer "how much
// wall-clock has elapsed since Play" reads Transport.
//
// PatternPlayer is a separate object with its OWN position counter. It
// advances each audio buffer, wraps at loopLengthSamples, and lets the
// walker + visual playhead read a position that never needs `mod`. The
// wrap point can change mid-play without teleporting the playhead:
//
//   * setLoopLengthSamples() with newLen >= currentPosition applies
//     immediately (extension is smooth — position keeps advancing).
//   * setLoopLengthSamples() with newLen  < currentPosition stashes the
//     change as pending and applies it at the next wrap boundary (shrink
//     without a mid-loop jump).
//
// Thread model mirrors Transport: audio thread calls beginBuffer/endBuffer
// bracketing the audio callback; UI thread writes via setters; both sides
// use atomics.
//
// MVP: one PatternPlayer instance owned by PluginHost. Later, when SONG
// mode or layered clips arrive, we'll spawn one per playing pattern — the
// class is designed for that with no changes to the audio-thread contract.

#include "Transport.h"

#include <atomic>
#include <cstdint>

namespace nasty {

class PatternPlayer {
public:
    // AUDIO THREAD. Bracket every audio callback with begin/end. bufferStart
    // captures the position that walkers should treat as "start of buffer";
    // endBuffer advances the counter iff the coupled Transport is playing
    // and past the count-in threshold.
    void beginBuffer(int numSamples, const Transport& transport) noexcept {
        bufferStartPosition = position.load(std::memory_order_acquire);
        bufferSizeSamples   = numSamples;

        const bool tPlaying = transport.getIsPlaying();
        const bool afterCountIn = transport.getBufferStartSample() >= 0;
        shouldAdvanceThisBuffer = tPlaying && afterCountIn;
    }
    void endBuffer() noexcept {
        if (!shouldAdvanceThisBuffer) return;
        const std::int64_t loopLen = loopLengthSamples.load(std::memory_order_acquire);
        std::int64_t newPos = bufferStartPosition + bufferSizeSamples;
        if (loopLen > 0 && newPos >= loopLen) {
            // Apply any pending loop-length change AT the wrap boundary so
            // shrinks don't yank the position backward mid-iteration.
            const std::int64_t pending = pendingLoopLengthSamples.exchange(
                0, std::memory_order_acq_rel);
            if (pending > 0) {
                loopLengthSamples.store(pending, std::memory_order_release);
                newPos %= pending;
            } else {
                newPos %= loopLen;
            }
        }
        position.store(newPos, std::memory_order_release);
    }

    // AUDIO THREAD READERS (valid between beginBuffer and endBuffer).
    std::int64_t getBufferStartPosition() const noexcept { return bufferStartPosition; }
    int          getBufferSize()          const noexcept { return bufferSizeSamples; }

    // ANY THREAD READERS.
    std::int64_t getPositionSample()      const noexcept { return position.load(std::memory_order_acquire); }
    std::int64_t getLoopLengthSamples()   const noexcept { return loopLengthSamples.load(std::memory_order_acquire); }
    std::int64_t getPendingLoopLengthSamples() const noexcept { return pendingLoopLengthSamples.load(std::memory_order_acquire); }

    // UI THREAD WRITERS.
    void seek(std::int64_t s) noexcept {
        position.store(s, std::memory_order_release);
        // A seek is an explicit big-transition from the UI — apply any
        // pending loop-length change now. Otherwise, transitions like
        // "linear record (loop=1e12) → normal play (loop=192000)" would
        // never resolve, because position would never cross the old 1e12
        // boundary to trigger the pending swap.
        const std::int64_t pending = pendingLoopLengthSamples.exchange(
            0, std::memory_order_acq_rel);
        if (pending > 0) {
            loopLengthSamples.store(pending, std::memory_order_release);
        }
    }
    void setLoopLengthSamples(std::int64_t newLen) noexcept {
        if (newLen <= 0) {
            loopLengthSamples.store(newLen, std::memory_order_release);
            pendingLoopLengthSamples.store(0, std::memory_order_release);
            return;
        }
        const std::int64_t pos = position.load(std::memory_order_acquire);
        if (newLen >= pos) {
            // Extension (or no change) — safe to apply immediately. Position
            // is still within the new loop bounds, walker keeps sweeping.
            loopLengthSamples.store(newLen, std::memory_order_release);
            pendingLoopLengthSamples.store(0, std::memory_order_release);
        } else {
            // Shrink below current position — defer to next wrap so the
            // playhead doesn't teleport backward mid-iteration.
            pendingLoopLengthSamples.store(newLen, std::memory_order_release);
        }
    }

private:
    std::atomic<std::int64_t> position{0};
    std::atomic<std::int64_t> loopLengthSamples{0};
    std::atomic<std::int64_t> pendingLoopLengthSamples{0};

    // Audio-thread scratch, only touched between beginBuffer/endBuffer.
    std::int64_t bufferStartPosition{0};
    int          bufferSizeSamples{0};
    bool         shouldAdvanceThisBuffer{false};
};

} // namespace nasty
