// Unit tests for nasty::PatternPlayer — the loop-state layer on top of
// Transport. Covers the invariants the walker + visual playhead rely on:
// advance-only-when-playing, count-in gating, immediate-extension vs
// deferred-shrink of the loop length, and seek flushing pending shrink.

#include "test_framework.h"
#include "../src/PatternPlayer.h"
#include "../src/Transport.h"

using nasty::PatternPlayer;
using nasty::Transport;

// Small helper: run one audio buffer through both objects with the
// canonical audio-callback bracketing.
static void tickBuffer(Transport& t, PatternPlayer& p, int samples) {
    t.beginBuffer(samples);
    p.beginBuffer(samples, t);
    p.endBuffer();
    t.endBuffer();
}

TEST(PatternPlayer_defaults) {
    PatternPlayer p;
    CHECK_EQ(p.getPositionSample(), 0);
    CHECK_EQ(p.getLoopLengthSamples(), 0);
    CHECK_EQ(p.getPendingLoopLengthSamples(), 0);
}

TEST(PatternPlayer_does_not_advance_when_transport_stopped) {
    Transport t;
    PatternPlayer p;
    p.setLoopLengthSamples(1000);
    // Transport not playing.
    tickBuffer(t, p, 256);
    CHECK_EQ(p.getPositionSample(), 0);
}

TEST(PatternPlayer_does_not_advance_during_count_in) {
    Transport t;
    PatternPlayer p;
    p.setLoopLengthSamples(1000);
    t.play();
    // Simulate count-in: transport sample counter is negative. beginBuffer
    // captures bufferStartSample from the atomic — set it directly via seek.
    t.seek(-512);
    tickBuffer(t, p, 512);
    CHECK_EQ(p.getPositionSample(), 0);
}

TEST(PatternPlayer_advances_when_playing_past_count_in) {
    Transport t;
    PatternPlayer p;
    p.setLoopLengthSamples(1'000'000); // big enough not to wrap
    t.play();
    tickBuffer(t, p, 512);
    CHECK_EQ(p.getPositionSample(), 512);
    tickBuffer(t, p, 256);
    CHECK_EQ(p.getPositionSample(), 768);
}

TEST(PatternPlayer_wraps_at_loop_end) {
    Transport t;
    PatternPlayer p;
    p.setLoopLengthSamples(1000);
    t.play();
    // Advance to position 900.
    for (int i = 0; i < 9; ++i) tickBuffer(t, p, 100);
    CHECK_EQ(p.getPositionSample(), 900);
    // Next 200-sample buffer crosses the loop boundary. 900+200 = 1100 %% 1000 = 100.
    tickBuffer(t, p, 200);
    CHECK_EQ(p.getPositionSample(), 100);
}

TEST(PatternPlayer_extension_applies_immediately) {
    Transport t;
    PatternPlayer p;
    p.setLoopLengthSamples(1000);
    t.play();
    for (int i = 0; i < 5; ++i) tickBuffer(t, p, 100); // pos = 500
    // Extend to 2000 — pos (500) is well within, apply immediately.
    p.setLoopLengthSamples(2000);
    CHECK_EQ(p.getLoopLengthSamples(), 2000);
    CHECK_EQ(p.getPendingLoopLengthSamples(), 0);
    // No wrap over the next few buffers even though we'd have wrapped at 1000.
    for (int i = 0; i < 10; ++i) tickBuffer(t, p, 100);
    CHECK_EQ(p.getPositionSample(), 1500);
}

TEST(PatternPlayer_shrink_below_position_defers_to_wrap) {
    Transport t;
    PatternPlayer p;
    p.setLoopLengthSamples(2000);
    t.play();
    for (int i = 0; i < 15; ++i) tickBuffer(t, p, 100); // pos = 1500
    // Shrink to 1000 — pos (1500) is past that; must NOT teleport backward.
    p.setLoopLengthSamples(1000);
    CHECK_EQ(p.getLoopLengthSamples(), 2000);          // unchanged
    CHECK_EQ(p.getPendingLoopLengthSamples(), 1000);   // stashed
    // Keep playing until the old loop wraps. 1500 → 1900 → 2000-wrap.
    for (int i = 0; i < 4; ++i) tickBuffer(t, p, 100); // pos = 1900
    CHECK_EQ(p.getPositionSample(), 1900);
    tickBuffer(t, p, 200);
    // Wrapped: pending applied. New loop is 1000. 1900+200 = 2100 %% 1000 = 100.
    CHECK_EQ(p.getLoopLengthSamples(), 1000);
    CHECK_EQ(p.getPendingLoopLengthSamples(), 0);
    CHECK_EQ(p.getPositionSample(), 100);
}

TEST(PatternPlayer_seek_flushes_pending_shrink) {
    Transport t;
    PatternPlayer p;
    p.setLoopLengthSamples(2000);
    t.play();
    for (int i = 0; i < 15; ++i) tickBuffer(t, p, 100); // pos = 1500
    p.setLoopLengthSamples(1000);
    CHECK_EQ(p.getPendingLoopLengthSamples(), 1000);
    // Explicit UI seek should flush the pending change now.
    p.seek(200);
    CHECK_EQ(p.getPositionSample(), 200);
    CHECK_EQ(p.getLoopLengthSamples(), 1000);
    CHECK_EQ(p.getPendingLoopLengthSamples(), 0);
}

TEST(PatternPlayer_zero_or_negative_loop_clears_pending) {
    Transport t;
    PatternPlayer p;
    p.setLoopLengthSamples(2000);
    t.play();
    for (int i = 0; i < 15; ++i) tickBuffer(t, p, 100); // pos = 1500
    p.setLoopLengthSamples(1000);
    CHECK_EQ(p.getPendingLoopLengthSamples(), 1000);
    // Setting loop <= 0 must clear pending too (e.g. "no loop / linear").
    p.setLoopLengthSamples(0);
    CHECK_EQ(p.getLoopLengthSamples(), 0);
    CHECK_EQ(p.getPendingLoopLengthSamples(), 0);
}

TEST(PatternPlayer_extension_equal_to_position_applies_immediately) {
    // Edge case: newLen == currentPosition. The "extension applies now"
    // branch uses >= so this must apply immediately, not defer.
    Transport t;
    PatternPlayer p;
    p.setLoopLengthSamples(2000);
    t.play();
    for (int i = 0; i < 10; ++i) tickBuffer(t, p, 100); // pos = 1000
    p.setLoopLengthSamples(1000);
    CHECK_EQ(p.getLoopLengthSamples(), 1000);
    CHECK_EQ(p.getPendingLoopLengthSamples(), 0);
}

