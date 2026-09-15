// Unit tests for nasty::Transport — the engine's monotonic sample counter.
// Covers the invariants callers rely on: reads/writes round-trip, buffer
// bracket math advances the counter iff playing, and stop() freezes cleanly.

#include "test_framework.h"
#include "../src/Transport.h"

using nasty::Transport;

TEST(Transport_defaults) {
    Transport t;
    CHECK_EQ(t.getCurrentSample(), 0);
    CHECK(!t.getIsPlaying());
    CHECK(t.getTempoBpm() == 120.0);
    CHECK_EQ(t.getLoopLengthSamples(), 0);
    CHECK(t.getSampleRate() == 48000.0);
    CHECK(t.getMode() == Transport::Mode::PAT);
}

TEST(Transport_play_stop) {
    Transport t;
    t.play();
    CHECK(t.getIsPlaying());
    t.stop();
    CHECK(!t.getIsPlaying());
}

TEST(Transport_seek_roundtrips) {
    Transport t;
    t.seek(12345);
    CHECK_EQ(t.getCurrentSample(), 12345);
    t.seek(0);
    CHECK_EQ(t.getCurrentSample(), 0);
}

TEST(Transport_setters_roundtrip) {
    Transport t;
    t.setTempo(140.5);
    CHECK(t.getTempoBpm() == 140.5);
    t.setLoopLengthSamples(96000);
    CHECK_EQ(t.getLoopLengthSamples(), 96000);
    t.setSampleRate(44100.0);
    CHECK(t.getSampleRate() == 44100.0);
    t.setMode(Transport::Mode::SONG);
    CHECK(t.getMode() == Transport::Mode::SONG);
}

TEST(Transport_stopped_buffer_does_not_advance) {
    Transport t;
    t.beginBuffer(512);
    CHECK_EQ(t.getBufferStartSample(), 0);
    CHECK_EQ(t.getBufferSize(), 512);
    t.endBuffer();
    CHECK_EQ(t.getCurrentSample(), 0);
}

TEST(Transport_playing_buffer_advances_by_size) {
    Transport t;
    t.play();
    t.beginBuffer(512);
    t.endBuffer();
    CHECK_EQ(t.getCurrentSample(), 512);
    t.beginBuffer(256);
    t.endBuffer();
    CHECK_EQ(t.getCurrentSample(), 768);
}

TEST(Transport_stop_freezes_position_across_buffers) {
    Transport t;
    t.play();
    t.beginBuffer(1024);
    t.endBuffer();
    CHECK_EQ(t.getCurrentSample(), 1024);
    t.stop();
    t.beginBuffer(1024);
    t.endBuffer();
    // Stopped: counter must not move.
    CHECK_EQ(t.getCurrentSample(), 1024);
}

TEST(Transport_seek_during_buffer_visible_to_next_bracket) {
    Transport t;
    t.play();
    t.beginBuffer(512);
    t.endBuffer();
    // UI seeks between buffers.
    t.seek(1'000'000);
    t.beginBuffer(512);
    // beginBuffer captured the post-seek value.
    CHECK_EQ(t.getBufferStartSample(), 1'000'000);
    t.endBuffer();
    CHECK_EQ(t.getCurrentSample(), 1'000'512);
}

TEST(Transport_monotonic_across_many_buffers) {
    Transport t;
    t.play();
    for (int i = 0; i < 100; ++i) {
        t.beginBuffer(512);
        t.endBuffer();
    }
    CHECK_EQ(t.getCurrentSample(), 100 * 512);
}
