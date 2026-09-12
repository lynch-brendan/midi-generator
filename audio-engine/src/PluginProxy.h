#pragma once

// PluginProxy — the graph-side half of plugin isolation.
//
// Replaces the real plugin node in the AudioProcessorGraph. Its processBlock
// shuttles audio + MIDI over the shared-memory ring buffer to a worker
// subprocess (nasty-plugin-worker) that hosts the actual plugin.
//
// Pipelined semantics: engine writes buffer N's input and reads buffer N-1's
// output in the same call. Worker produces one buffer behind. Cost: one
// buffer of latency (~10 ms at 512/48k). Benefit: the audio thread NEVER
// blocks on the worker, so a stalled or crashed plugin can't glitch the
// entire mix.
//
// Crash handling: if the worker dies unexpectedly, the notification pipe
// closes. The proxy detects this on its next attempted read and flips into
// "dead" mode: fills output with silence forever until the channel is
// reloaded. No panic on the audio thread; the proxy just becomes a
// passthrough-to-silence.

#include <juce_audio_processors/juce_audio_processors.h>
#include "PluginSandbox.h"

#include <atomic>
#include <condition_variable>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <sys/types.h>

namespace nasty::sandbox {

// Spawn a plugin worker as a child process and set up the SHM + pipe pair
// for it. On success returns a fully-formed ProxyProcessor ready to be
// added to the graph. Returns nullptr on any spawn failure.
//
// pluginDesc is written to a temp file so the worker can read it back —
// avoids a fragile stringly-typed argv or a second scan pass in the child.
// presetName + base64State are applied by the worker after prepareToPlay,
// matching the in-process load semantics (state first, preset overrides).
class PluginProxy;
std::unique_ptr<PluginProxy> spawnWorkerAndBuildProxy(
    const juce::PluginDescription& pluginDesc,
    double sampleRate,
    int    blockFrames,
    const juce::File& workerBinary,
    const juce::String& presetName,
    const juce::String& base64State,
    juce::String& errOut);

// The graph-side proxy. One per loaded plugin. Owns:
//   * a shared-memory segment mmap'd from a POSIX shm name
//   * two anonymous pipe fds (engine→worker wake, worker→engine wake)
//   * the child process pid (for reap on shutdown / crash)
class PluginProxy : public juce::AudioProcessor {
public:
    PluginProxy(SharedPluginBlock* shm,
                std::string shmName,
                int wakeWorkerFd,       // write end — engine writes 1 byte to kick worker
                int wakeEngineFd,       // read  end — engine reads worker's ack
                int ctrlWriteFd,        // engine → worker JSON control (line-delimited)
                int ctrlReadFd,         // worker → engine JSON control
                pid_t workerPid,
                juce::String pluginName,
                int inChannels,
                int outChannels)
        : juce::AudioProcessor(BusesProperties()
              .withInput ("In",  juce::AudioChannelSet::canonicalChannelSet(inChannels),  true)
              .withOutput("Out", juce::AudioChannelSet::canonicalChannelSet(outChannels), true)),
          shm_(shm), shmName_(std::move(shmName)),
          wakeWorkerFd_(wakeWorkerFd), wakeEngineFd_(wakeEngineFd),
          ctrlWriteFd_(ctrlWriteFd), ctrlReadFd_(ctrlReadFd),
          workerPid_(workerPid), pluginName_(std::move(pluginName)),
          numInputChannels_(inChannels), numOutputChannels_(outChannels) {}

    ~PluginProxy() override;

    // --- AudioProcessor overrides ---
    const juce::String getName() const override        { return pluginName_; }
    void prepareToPlay(double sr, int blockSize) override;
    void releaseResources() override                    {}
    bool acceptsMidi() const override                   { return true; }
    bool producesMidi() const override                  { return false; }
    double getTailLengthSeconds() const override        { return 0.0; }

    // The hot path. Real-time safe: no allocations, no locks, no blocking
    // syscalls — the pipe write is non-blocking with a full-buffer drop.
    void processBlock(juce::AudioBuffer<float>&  buf, juce::MidiBuffer& midi) override;
    void processBlock(juce::AudioBuffer<double>& buf, juce::MidiBuffer& midi) override;
    using AudioProcessor::processBlock;

    // No editor — the plugin's own editor lives inside the worker process
    // and is shown/hidden via the control channel.
    juce::AudioProcessorEditor* createEditor() override { return nullptr; }
    bool hasEditor() const override                    { return false; }
    int  getNumPrograms() override                     { return 1; }
    int  getCurrentProgram() override                  { return 0; }
    void setCurrentProgram(int) override               {}
    const juce::String getProgramName(int) override    { return {}; }
    void changeProgramName(int, const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override {}
    void setStateInformation(const void*, int) override {}

    // Diagnostic: has the worker died?
    bool isWorkerAlive() const noexcept {
        return workerAlive_.load(std::memory_order_relaxed);
    }

    // Fire-and-forget control-channel send. JSON line, newline-terminated.
    // Called from the engine's message thread — do NOT call from the audio
    // thread; writes may briefly block on pipe backpressure.
    void sendControl(const juce::var& msg);

    // Convenience wrappers matching the in-process control surface.
    void setParam(int paramIndex, float value01);
    void setProgram(int programIndex);
    void setPresetByName(const juce::String& name);
    void showEditor();
    void hideEditor();

    // Kick off the worker → engine event reader thread. Idempotent; called
    // once by spawnWorkerAndBuildProxy after the proxy is constructed.
    void startEventReader();

    // Synchronous request-response: ask the worker for its parameter list.
    // Blocks the CALLING thread until the response arrives or timeoutMs
    // elapses. Must NOT be called from the audio thread. Returns an empty
    // array on timeout or dead worker.
    juce::var queryParams(int timeoutMs = 500);

    // Synchronous request-response: ask the worker to serialise its plugin
    // state via getStateInformation and return a base64 blob. Used by song
    // save. Empty string on timeout or dead worker.
    juce::String queryState(int timeoutMs = 2000);

    // Cached copy of the last queryParams response. Populated by
    // spawnWorkerAndBuildProxy once at startup so paramsForOwner can serve
    // Claude synchronously without another round-trip.
    juce::var cachedParams() const { return cachedParams_; }
    void setCachedParams(const juce::var& v) { cachedParams_ = v; }

private:
    // Signal the worker with a non-blocking write. If the pipe buffer is
    // full (worker not keeping up), we drop the wake — it will pick up on
    // the next buffer anyway.
    void kickWorker() noexcept;

    // Read the worker's ack byte non-blocking. If the pipe returns EOF
    // (worker died), flip the alive flag. Never blocks.
    void drainAcks() noexcept;

    SharedPluginBlock* shm_ = nullptr;
    std::string  shmName_;
    int          wakeWorkerFd_ = -1;
    int          wakeEngineFd_ = -1;
    int          ctrlWriteFd_  = -1;
    int          ctrlReadFd_   = -1;
    pid_t        workerPid_    = -1;
    juce::String pluginName_;
    int          numInputChannels_  = 2;
    int          numOutputChannels_ = 2;

    std::atomic<bool> workerAlive_{true};
    uint64_t nextSeq_ = 0; // monotonic per-buffer counter
    juce::var cachedParams_ = juce::var(juce::Array<juce::var>{});

    // Reader thread for worker → engine events. Populates pendingResponses_
    // when it sees an event whose "reqId" matches an outstanding request.
    std::thread            eventReader_;
    std::atomic<bool>      eventReaderStop_{false};
    std::mutex             pendingMutex_;
    std::condition_variable pendingCv_;
    std::map<int, juce::var> pendingResponses_;
    std::atomic<int>       nextReqId_{1};
};

} // namespace nasty::sandbox
