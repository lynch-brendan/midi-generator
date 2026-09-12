#pragma once

// Plugin sandbox IPC primitive — shared memory + pipe-notification block
// used to shuttle audio, MIDI, and control between the main engine and a
// per-plugin worker subprocess.
//
// Design shape (matches Bitwig / Reaper's bridge):
//   * One SharedPluginBlock per plugin instance, mmap'd by both the engine
//     and its worker child.
//   * Pipelined: engine writes buffer N's input, then reads buffer N-1's
//     output. Worker computes one buffer behind. Costs one buffer of
//     latency but the audio thread NEVER blocks on the worker.
//   * Notification: a POSIX pipe pair. Engine writes 1 byte after staging
//     input; worker's audio loop blocks on read() and processes on wake.
//     Worker writes 1 byte back after staging output.
//   * Crash handling: worker death closes the pipe → engine's next read
//     returns EOF → engine marks the plugin dead and pumps silence.
//
// All shared fields are atomic where cross-process synchronization matters.
// The seq counters are the source of truth: producer stores data then
// increments seq with release semantics; consumer loads seq with acquire
// then reads data.

#include <atomic>
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <type_traits>

namespace nasty::sandbox {

// Upper bounds. Generous — a plugin block never uses more than a small
// fraction of this, and reserving the space up front means the SHM layout
// is a POD with no dynamic sizing per plugin. Cost: ~200 KB per plugin
// instance of RAM (backing store is disk-backed shared memory, mostly
// paged out in practice).
inline constexpr uint32_t kMaxChannels    = 8;      // stereo + surround headroom
inline constexpr uint32_t kMaxBlockFrames = 4096;   // very generous for a DAW
inline constexpr uint32_t kMaxMidiBytes   = 16384;  // ~2k noteOn/off events

// Fixed-size event packet for MIDI. Matches what juce::MidiMessage exposes:
// small (~3 byte) messages inline; larger sysex would need overflow, which
// we don't handle in v1 (plugins that receive sysex are rare in the
// pattern-playback path).
struct MidiEvent {
    uint32_t sample_offset;   // offset within the buffer, 0..block_size-1
    uint16_t byte_count;      // 1..3 for standard MIDI
    uint8_t  bytes[3];
    uint8_t  _pad;
};
inline constexpr uint32_t kMaxMidiEvents = kMaxMidiBytes / sizeof(MidiEvent);

// The shared block. Single instance per plugin, mmap'd R/W in both processes.
// POD layout — no vtables, no owning pointers, safe for cross-process access.
struct SharedPluginBlock {
    // ---- Session-level metadata (set once by engine at startup) ----
    std::atomic<uint32_t> block_frames;         // set by engine per prepareToPlay
    std::atomic<uint32_t> num_input_channels;
    std::atomic<uint32_t> num_output_channels;
    std::atomic<double>   sample_rate;

    // ---- Engine → worker: input for buffer N ----
    // Bumped by the engine after staging input_audio + input_midi. Worker
    // uses this to know a new buffer is ready. Pipe notification wakes the
    // worker; seq is the memory-order fence.
    std::atomic<uint64_t> input_seq;
    uint32_t              input_midi_event_count;
    MidiEvent             input_midi_events[kMaxMidiEvents];
    // Interleaved by channel, then frame: audio[ch * frames + frame].
    float                 input_audio[kMaxChannels * kMaxBlockFrames];

    // ---- Worker → engine: output for buffer N ----
    // Bumped by the worker after staging output_audio. Engine reads
    // output_seq to know the worker has produced. In pipelined mode the
    // engine expects output_seq == last_input_seq - 1.
    std::atomic<uint64_t> output_seq;
    float                 output_audio[kMaxChannels * kMaxBlockFrames];

    // ---- Playhead / tempo sync (engine writes each buffer, worker reads) ----
    // Small subset of juce::AudioPlayHead::PositionInfo. Covers 95% of
    // tempo-synced plugins (arp rate, sync'd delay/reverb, tempo LFOs).
    // Missing (fill in as needed): loop range, time-sig, PPQ of last bar,
    // frame rate, host bar count. Written every processBlock by the proxy;
    // fresh values every buffer means we don't need atomic ordering — the
    // worker sees a slightly-lagged coherent snapshot, good enough.
    std::atomic<double>   ph_bpm;
    std::atomic<uint32_t> ph_is_playing;      // bool in a stable-layout POD
    std::atomic<int64_t>  ph_time_samples;    // monotonic session sample
    std::atomic<double>   ph_time_seconds;    // seconds since session start
    std::atomic<double>   ph_ppq_position;    // bars.beats (in quarter notes)

    // ---- Lifecycle / crash signaling ----
    // Worker sets alive=false on graceful shutdown; unexpected death is
    // detected via the notification pipe closing. Engine checks this on
    // every buffer's read fence.
    std::atomic<uint32_t> worker_alive;

    void reset() {
        block_frames.store(0);
        num_input_channels.store(2);
        num_output_channels.store(2);
        sample_rate.store(48000.0);
        input_seq.store(0);
        output_seq.store(0);
        input_midi_event_count = 0;
        ph_bpm.store(120.0);
        ph_is_playing.store(0);
        ph_time_samples.store(0);
        ph_time_seconds.store(0.0);
        ph_ppq_position.store(0.0);
        worker_alive.store(1);
        // Zero audio buffers so the first buffer's silence is real zeros,
        // not whatever was in the OS's freshly-mmap'd page.
        std::memset(input_audio, 0, sizeof(input_audio));
        std::memset(output_audio, 0, sizeof(output_audio));
    }
};

static_assert(std::is_standard_layout_v<SharedPluginBlock>,
              "SharedPluginBlock must be a POD-ish standard-layout type — "
              "cross-process mmap depends on identical layout in both binaries");

// Size in bytes we'll reserve per plugin instance in SHM.
inline constexpr size_t kSharedBlockBytes = sizeof(SharedPluginBlock);

// SHM name / pipe fd handoff between engine and worker happens over argv.
// argv format (worker binary):
//   nasty-plugin-worker <shm_name> <engine_to_worker_fd> <worker_to_engine_fd> <plugin_id> <sample_rate> <block_frames>
// The two fd numbers refer to the read ends passed via unix-domain fd
// passing OR — simpler and what we use — to raw fds inherited by the child
// via posix_spawn's file_actions dup2. Anonymous pipes: engine keeps the
// write end of one and read end of the other; worker inherits the
// complementary pair.

} // namespace nasty::sandbox
