#include "PluginProxy.h"

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <signal.h>
#include <spawn.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

extern char** environ;

namespace nasty::sandbox {

// ---- ProxyProcessor ----

PluginProxy::~PluginProxy() {
    // Ask the event reader to exit and wake any pending requesters so they
    // don't wait for a response that will never come.
    eventReaderStop_.store(true, std::memory_order_release);
    {
        std::lock_guard<std::mutex> g(pendingMutex_);
        pendingCv_.notify_all();
    }
    // Closing our end of the worker → engine control pipe unblocks its
    // read loop → thread exits.
    if (ctrlReadFd_ >= 0) {
        ::close(ctrlReadFd_);
        ctrlReadFd_ = -1;
    }
    if (eventReader_.joinable()) eventReader_.join();

    // Ask the worker to exit by closing our end of its input pipe. Its
    // blocking read() returns 0, it falls through the loop and exits
    // cleanly. If it doesn't, we escalate to SIGTERM after a short grace.
    if (wakeWorkerFd_ >= 0) {
        ::close(wakeWorkerFd_);
        wakeWorkerFd_ = -1;
    }
    if (wakeEngineFd_ >= 0) {
        ::close(wakeEngineFd_);
        wakeEngineFd_ = -1;
    }
    if (ctrlWriteFd_ >= 0) {
        ::close(ctrlWriteFd_);
        ctrlWriteFd_ = -1;
    }
    if (ctrlReadFd_ >= 0) {
        ::close(ctrlReadFd_);
        ctrlReadFd_ = -1;
    }
    if (workerPid_ > 0) {
        int status = 0;
        // Non-blocking wait first. If the child is already gone (crashed
        // earlier), reap it. Otherwise give it a moment then SIGTERM.
        pid_t r = ::waitpid(workerPid_, &status, WNOHANG);
        if (r == 0) {
            ::kill(workerPid_, SIGTERM);
            for (int i = 0; i < 20; ++i) { // ~200 ms grace
                if (::waitpid(workerPid_, &status, WNOHANG) != 0) break;
                usleep(10 * 1000);
            }
            // Escalate to SIGKILL if it still hasn't exited.
            if (::waitpid(workerPid_, &status, WNOHANG) == 0) {
                ::kill(workerPid_, SIGKILL);
                ::waitpid(workerPid_, &status, 0);
            }
        }
        workerPid_ = -1;
    }
    if (shm_ != nullptr) {
        ::munmap(shm_, kSharedBlockBytes);
        shm_ = nullptr;
    }
    if (!shmName_.empty()) {
        ::shm_unlink(shmName_.c_str());
        shmName_.clear();
    }
}

void PluginProxy::prepareToPlay(double sr, int blockSize) {
    // Publish sample rate + block size to the worker via SHM. The worker
    // uses these for prepareToPlay on the real plugin. Session-level;
    // rarely changes after startup.
    if (shm_) {
        shm_->sample_rate.store(sr, std::memory_order_release);
        shm_->block_frames.store((uint32_t) blockSize, std::memory_order_release);
        shm_->num_input_channels.store((uint32_t) numInputChannels_,  std::memory_order_release);
        shm_->num_output_channels.store((uint32_t) numOutputChannels_, std::memory_order_release);
    }
}

void PluginProxy::kickWorker() noexcept {
    if (wakeWorkerFd_ < 0) return;
    const char b = 1;
    // Non-blocking write. If the pipe is full the worker is behind — drop
    // the wake, it'll process on its current cycle anyway.
    ssize_t r = ::write(wakeWorkerFd_, &b, 1);
    (void) r;
}

void PluginProxy::drainAcks() noexcept {
    if (wakeEngineFd_ < 0) return;
    // Read all available ack bytes so we don't wake up stale ones. We
    // don't care about the value; the seq counter is the truth.
    char buf[16];
    ssize_t r;
    while ((r = ::read(wakeEngineFd_, buf, sizeof(buf))) > 0) { /* drain */ }
    if (r == 0) {
        // EOF: worker closed its end. It's dead.
        workerAlive_.store(false, std::memory_order_release);
    } else if (r < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {
        // Any error other than "no data right now" is fatal for the pipe.
        workerAlive_.store(false, std::memory_order_release);
    }
}

void PluginProxy::processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer& midi) {
    const int frames = buf.getNumSamples();
    const int nInCh  = std::min<int>(buf.getNumChannels(), (int) kMaxChannels);
    const int nOutCh = nInCh;

    if (!shm_ || !workerAlive_.load(std::memory_order_relaxed) || frames > (int) kMaxBlockFrames) {
        // Dead worker or oversize block — silence.
        static thread_local int silenceLogged = 0;
        if (++silenceLogged < 3) {
            std::fprintf(stderr, "[proxy %s] silent path shm=%p alive=%d frames=%d\n",
                         pluginName_.toRawUTF8(), (void*) shm_,
                         (int) workerAlive_.load(std::memory_order_relaxed), frames);
        }
        buf.clear();
        return;
    }
    if (nextSeq_ == 0) {
        std::fprintf(stderr, "[proxy %s] first processBlock frames=%d nMidi=%d\n",
                     pluginName_.toRawUTF8(), frames, midi.getNumEvents());
    }

    // Non-blocking drain of any pending acks; catches death.
    drainAcks();

    // Forward host playhead into SHM so tempo-synced plugins (arps, sync'd
    // delays, LFOs) inside the worker see the engine's transport state.
    // Fresh values every buffer; no atomic ordering fence needed because
    // each field is single-word atomic and the worker only reads the
    // current snapshot, not the delta.
    if (auto* ph = getPlayHead()) {
        if (auto info = ph->getPosition()) {
            shm_->ph_bpm.store(info->getBpm().orFallback(120.0),
                               std::memory_order_relaxed);
            shm_->ph_is_playing.store(info->getIsPlaying() ? 1u : 0u,
                                      std::memory_order_relaxed);
            shm_->ph_time_samples.store((int64_t) info->getTimeInSamples().orFallback(0),
                                        std::memory_order_relaxed);
            shm_->ph_time_seconds.store(info->getTimeInSeconds().orFallback(0.0),
                                        std::memory_order_relaxed);
            shm_->ph_ppq_position.store(info->getPpqPosition().orFallback(0.0),
                                        std::memory_order_relaxed);
        }
    }

    // Copy input audio into SHM by channel. Deinterleaved storage means
    // one memcpy per channel; safe from the audio thread (no allocation).
    for (int c = 0; c < nInCh; ++c) {
        std::memcpy(shm_->input_audio + c * (size_t) kMaxBlockFrames,
                    buf.getReadPointer(c),
                    (size_t) frames * sizeof(float));
    }

    // Serialize MIDI into the fixed-size event array. We drop events that
    // don't fit; that's a bug-report scenario, not a real-world one —
    // 2000 events per buffer is way past any plugin's saturation point.
    uint32_t nEvents = 0;
    for (const auto meta : midi) {
        if (nEvents >= kMaxMidiEvents) break;
        const auto& m = meta.getMessage();
        const int   sz = m.getRawDataSize();
        if (sz < 1 || sz > 3) continue; // sysex etc. skipped
        auto& e = shm_->input_midi_events[nEvents++];
        e.sample_offset = (uint32_t) meta.samplePosition;
        e.byte_count    = (uint16_t) sz;
        std::memcpy(e.bytes, m.getRawData(), (size_t) sz);
    }
    shm_->input_midi_event_count = nEvents;

    // Bump input_seq with release so the worker sees a coherent snapshot.
    const uint64_t seq = ++nextSeq_;
    shm_->input_seq.store(seq, std::memory_order_release);
    kickWorker();

    // Read the LATEST output the worker has produced. In pipelined mode
    // this is seq-1 (or earlier if worker is behind). If nothing is ready,
    // output silence for this buffer.
    const uint64_t outSeq = shm_->output_seq.load(std::memory_order_acquire);
    if (outSeq == 0) {
        // Worker hasn't produced anything yet (first buffers after spawn).
        buf.clear();
    } else {
        for (int c = 0; c < nOutCh; ++c) {
            std::memcpy(buf.getWritePointer(c),
                        shm_->output_audio + c * (size_t) kMaxBlockFrames,
                        (size_t) frames * sizeof(float));
        }
    }

    // Downstream expects MIDI to have been consumed by the plugin — the
    // real plugin runs inside the worker so it never sees this buffer's
    // events. Clear so the graph doesn't re-route them somewhere else.
    midi.clear();
}

void PluginProxy::processBlock(juce::AudioBuffer<double>& buf, juce::MidiBuffer& midi) {
    // Double-precision path — just convert to float, process, convert back.
    // Plugin bridging fundamentally can't preserve doubles across the
    // ring; the worker's processBlock is float-only.
    juce::AudioBuffer<float> tmp(buf.getNumChannels(), buf.getNumSamples());
    for (int c = 0; c < buf.getNumChannels(); ++c) {
        const double* src = buf.getReadPointer(c);
        float* dst = tmp.getWritePointer(c);
        for (int i = 0; i < buf.getNumSamples(); ++i)
            dst[i] = (float) src[i];
    }
    processBlock(tmp, midi);
    for (int c = 0; c < buf.getNumChannels(); ++c) {
        const float* src = tmp.getReadPointer(c);
        double* dst = buf.getWritePointer(c);
        for (int i = 0; i < buf.getNumSamples(); ++i)
            dst[i] = (double) src[i];
    }
}

// ---- Control-channel senders ----
// Fire-and-forget JSON over the engine → worker control pipe. The pipe was
// set non-blocking on our end at spawn time, but JSON lines are small
// enough that pipe backpressure isn't a realistic concern for these
// message rates (a couple per second at absolute worst). If the worker is
// dead the write returns -1 with EPIPE — we silently swallow it, the
// audio-thread drain path already flipped workerAlive_ on the pipe EOF.

void PluginProxy::sendControl(const juce::var& msg) {
    if (ctrlWriteFd_ < 0) return;
    if (!workerAlive_.load(std::memory_order_relaxed)) return;
    juce::String line = juce::JSON::toString(msg, /*allOnOneLine*/ true) + "\n";
    const auto bytes = line.toRawUTF8();
    const size_t sz = std::strlen(bytes);
    ssize_t r = ::write(ctrlWriteFd_, bytes, sz);
    (void) r;
}

void PluginProxy::setParam(int paramIndex, float value01) {
    auto* o = new juce::DynamicObject();
    o->setProperty("cmd",   juce::var("set_param"));
    o->setProperty("index", juce::var(paramIndex));
    o->setProperty("value", juce::var((double) value01));
    sendControl(juce::var(o));
}

void PluginProxy::setProgram(int programIndex) {
    auto* o = new juce::DynamicObject();
    o->setProperty("cmd",   juce::var("set_program"));
    o->setProperty("index", juce::var(programIndex));
    sendControl(juce::var(o));
}

void PluginProxy::setPresetByName(const juce::String& name) {
    auto* o = new juce::DynamicObject();
    o->setProperty("cmd",  juce::var("set_preset_by_name"));
    o->setProperty("name", juce::var(name));
    sendControl(juce::var(o));
}

void PluginProxy::showEditor() {
    auto* o = new juce::DynamicObject();
    o->setProperty("cmd", juce::var("show_ui"));
    sendControl(juce::var(o));
}

void PluginProxy::hideEditor() {
    auto* o = new juce::DynamicObject();
    o->setProperty("cmd", juce::var("hide_ui"));
    sendControl(juce::var(o));
}

// Reader thread: pulls JSON lines from the worker → engine control pipe
// and posts them into pendingResponses_ keyed by reqId. Sync callers
// (queryParams etc.) wait on pendingCv_ until their reqId lands.
void PluginProxy::startEventReader() {
    eventReader_ = std::thread([this]() {
        juce::String buf;
        char chunk[1024];
        while (!eventReaderStop_.load(std::memory_order_relaxed)) {
            ssize_t r = ::read(ctrlReadFd_, chunk, sizeof(chunk));
            if (r <= 0) {
                if (r == 0) {
                    workerAlive_.store(false, std::memory_order_release);
                    break;
                }
                if (errno == EAGAIN || errno == EWOULDBLOCK) {
                    // Non-blocking read with nothing pending — brief nap.
                    usleep(2 * 1000);
                    continue;
                }
                workerAlive_.store(false, std::memory_order_release);
                break;
            }
            buf += juce::String::fromUTF8(chunk, (int) r);
            for (;;) {
                const int nl = buf.indexOfChar('\n');
                if (nl < 0) break;
                juce::String line = buf.substring(0, nl);
                buf = buf.substring(nl + 1);
                juce::var msg = juce::JSON::parse(line);
                if (!msg.isObject()) continue;
                if (msg.hasProperty("reqId")) {
                    const int reqId = (int) msg["reqId"];
                    std::lock_guard<std::mutex> g(pendingMutex_);
                    pendingResponses_[reqId] = msg;
                    pendingCv_.notify_all();
                }
                // No-reqId events (worker_ready etc.) are informational for
                // now. Future: route to a callback.
            }
        }
        // Wake anyone waiting so they can time out and return.
        {
            std::lock_guard<std::mutex> g(pendingMutex_);
            pendingCv_.notify_all();
        }
    });
}

juce::var PluginProxy::queryParams(int timeoutMs) {
    std::fprintf(stderr, "[queryParams] enter\n");
    if (!workerAlive_.load(std::memory_order_relaxed)) {
        std::fprintf(stderr, "[queryParams] worker dead, empty\n");
        return juce::var(juce::Array<juce::var>{});
    }

    const int reqId = nextReqId_.fetch_add(1, std::memory_order_relaxed);
    std::fprintf(stderr, "[queryParams] reqId=%d, building msg\n", reqId);
    auto* o = new juce::DynamicObject();
    o->setProperty("cmd",   juce::var("get_params"));
    o->setProperty("reqId", juce::var(reqId));
    std::fprintf(stderr, "[queryParams] pre sendControl\n");
    sendControl(juce::var(o));
    std::fprintf(stderr, "[queryParams] post sendControl, pre wait\n");

    std::unique_lock<std::mutex> lk(pendingMutex_);
    const bool got = pendingCv_.wait_for(lk, std::chrono::milliseconds(timeoutMs),
        [this, reqId]() {
            return pendingResponses_.find(reqId) != pendingResponses_.end()
                || !workerAlive_.load(std::memory_order_relaxed)
                || eventReaderStop_.load(std::memory_order_relaxed);
        });
    std::fprintf(stderr, "[queryParams] wait done got=%d\n", (int) got);
    if (!got) return juce::var(juce::Array<juce::var>{});
    auto it = pendingResponses_.find(reqId);
    if (it == pendingResponses_.end()) return juce::var(juce::Array<juce::var>{});
    juce::var response = it->second;
    pendingResponses_.erase(it);
    // Response shape: {"event":"params","reqId":N,"params":[...]}.
    return response["params"];
}

juce::String PluginProxy::queryState(int timeoutMs) {
    if (!workerAlive_.load(std::memory_order_relaxed)) return {};

    const int reqId = nextReqId_.fetch_add(1, std::memory_order_relaxed);
    auto* o = new juce::DynamicObject();
    o->setProperty("cmd",   juce::var("get_state"));
    o->setProperty("reqId", juce::var(reqId));
    sendControl(juce::var(o));

    std::unique_lock<std::mutex> lk(pendingMutex_);
    const bool got = pendingCv_.wait_for(lk, std::chrono::milliseconds(timeoutMs),
        [this, reqId]() {
            return pendingResponses_.find(reqId) != pendingResponses_.end()
                || !workerAlive_.load(std::memory_order_relaxed)
                || eventReaderStop_.load(std::memory_order_relaxed);
        });
    if (!got) return {};
    auto it = pendingResponses_.find(reqId);
    if (it == pendingResponses_.end()) return {};
    juce::var response = it->second;
    pendingResponses_.erase(it);
    // Response shape: {"event":"state","reqId":N,"base64":"..."}.
    return response["base64"].toString();
}

// ---- Spawn ----

// Set a pipe fd non-blocking. Fatal to isolation guarantees if it doesn't
// take, so we log but keep going — the audio thread guards blocking with
// its own drain loop anyway.
static void setNonBlocking(int fd) {
    int flags = ::fcntl(fd, F_GETFL, 0);
    if (flags >= 0) ::fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

std::unique_ptr<PluginProxy> spawnWorkerAndBuildProxy(
    const juce::PluginDescription& desc,
    double sampleRate,
    int    blockFrames,
    const juce::File& workerBinary,
    const juce::String& presetName,
    const juce::String& base64State,
    juce::String& errOut) {

    std::fprintf(stderr, "[spawn] enter for %s\n", desc.name.toRawUTF8());
    if (!workerBinary.existsAsFile()) {
        errOut = "worker binary not found: " + workerBinary.getFullPathName();
        std::fprintf(stderr, "[spawn] worker binary missing at %s\n",
                     workerBinary.getFullPathName().toRawUTF8());
        return nullptr;
    }
    std::fprintf(stderr, "[spawn] worker binary ok\n");

    // Unique SHM name per plugin instance. Include pid + a counter so
    // reloads within one engine lifetime don't collide.
    static std::atomic<uint32_t> counter{0};
    const uint32_t c = counter.fetch_add(1, std::memory_order_relaxed);
    char shmName[64];
    std::snprintf(shmName, sizeof(shmName), "/nasty-plugin-%d-%u", (int) ::getpid(), c);

    int shmFd = ::shm_open(shmName, O_CREAT | O_RDWR, 0600);
    if (shmFd < 0) {
        errOut = "shm_open failed: " + juce::String(std::strerror(errno));
        return nullptr;
    }
    if (::ftruncate(shmFd, (off_t) kSharedBlockBytes) != 0) {
        errOut = "ftruncate failed: " + juce::String(std::strerror(errno));
        ::close(shmFd);
        ::shm_unlink(shmName);
        return nullptr;
    }
    void* mem = ::mmap(nullptr, kSharedBlockBytes, PROT_READ | PROT_WRITE,
                       MAP_SHARED, shmFd, 0);
    ::close(shmFd);
    if (mem == MAP_FAILED) {
        errOut = "mmap failed: " + juce::String(std::strerror(errno));
        ::shm_unlink(shmName);
        return nullptr;
    }
    auto* shm = new (mem) SharedPluginBlock();
    shm->reset();
    std::fprintf(stderr, "[spawn] shm ready name=%s size=%zu\n", shmName, kSharedBlockBytes);

    // Four anonymous pipes:
    //   e2w_audio: engine writes wake byte, worker reads (fd 3 in child)
    //   w2e_audio: worker writes wake byte, engine reads (fd 4 in child)
    //   e2w_ctrl:  engine → worker JSON control lines (fd 5 in child)
    //   w2e_ctrl:  worker → engine JSON events        (fd 6 in child)
    // Audio + control get separate pipes so a stalled control-message
    // handler in the worker can't backpressure the audio wake path.
    int e2w[2] = { -1, -1 };
    int w2e[2] = { -1, -1 };
    int e2wc[2] = { -1, -1 };
    int w2ec[2] = { -1, -1 };
    if (::pipe(e2w) != 0 || ::pipe(w2e) != 0
        || ::pipe(e2wc) != 0 || ::pipe(w2ec) != 0) {
        errOut = "pipe() failed: " + juce::String(std::strerror(errno));
        ::munmap(mem, kSharedBlockBytes);
        ::shm_unlink(shmName);
        return nullptr;
    }
    // Non-blocking on the engine-side ends of every pipe. Worker's are
    // blocking by default so its wait-for-wake / read-json calls block
    // cleanly. Non-blocking on the engine side keeps the audio thread's
    // drain path from ever stalling.
    setNonBlocking(e2w[1]);
    setNonBlocking(w2e[0]);
    setNonBlocking(e2wc[1]);
    setNonBlocking(w2ec[0]);
    std::fprintf(stderr, "[spawn] pipes set up\n");

    // Write plugin description to a temp file the worker reads at startup.
    auto tmp = juce::File::createTempFile(".pluginDesc.xml");
    if (auto xml = desc.createXml()) {
        xml->writeTo(tmp);
    } else {
        errOut = "PluginDescription::createXml returned null";
        ::close(e2w[0]); ::close(e2w[1]);
        ::close(w2e[0]); ::close(w2e[1]);
        ::munmap(mem, kSharedBlockBytes);
        ::shm_unlink(shmName);
        return nullptr;
    }

    // If restoring plugin state (song load), decode the base64 blob into a
    // temp file so we can hand the worker a path instead of an argv-embedded
    // blob (which could exceed argv size limits and is fragile to quote).
    juce::File stateFile;
    if (base64State.isNotEmpty()) {
        juce::MemoryOutputStream decoded;
        if (juce::Base64::convertFromBase64(decoded, base64State)
            && decoded.getDataSize() > 0) {
            stateFile = juce::File::createTempFile(".pluginState.bin");
            stateFile.replaceWithData(decoded.getData(), decoded.getDataSize());
        }
        // Bad blob → silently skip. Matches in-process behaviour: a corrupt
        // state shouldn't block load.
    }

    // Publish session params for prepareToPlay in the worker.
    shm->block_frames.store((uint32_t) blockFrames, std::memory_order_release);
    shm->sample_rate.store(sampleRate, std::memory_order_release);

    // posix_spawn with file_actions: worker inherits e2w[0]→fd3, w2e[1]→fd4,
    // e2wc[0]→fd5, w2ec[1]→fd6. Everything else gets closed in the child.
    posix_spawn_file_actions_t fa;
    ::posix_spawn_file_actions_init(&fa);
    ::posix_spawn_file_actions_adddup2(&fa, e2w[0],  3);
    ::posix_spawn_file_actions_adddup2(&fa, w2e[1],  4);
    ::posix_spawn_file_actions_adddup2(&fa, e2wc[0], 5);
    ::posix_spawn_file_actions_adddup2(&fa, w2ec[1], 6);
    // Close every parent-side end + every original of the dup'd fds so the
    // child inherits ONLY the four canonical fds 3/4/5/6.
    ::posix_spawn_file_actions_addclose(&fa, e2w[0]);
    ::posix_spawn_file_actions_addclose(&fa, e2w[1]);
    ::posix_spawn_file_actions_addclose(&fa, w2e[0]);
    ::posix_spawn_file_actions_addclose(&fa, w2e[1]);
    ::posix_spawn_file_actions_addclose(&fa, e2wc[0]);
    ::posix_spawn_file_actions_addclose(&fa, e2wc[1]);
    ::posix_spawn_file_actions_addclose(&fa, w2ec[0]);
    ::posix_spawn_file_actions_addclose(&fa, w2ec[1]);

    const juce::String binPath  = workerBinary.getFullPathName();
    const juce::String xmlPath  = tmp.getFullPathName();
    const juce::String srStr    = juce::String(sampleRate);
    const juce::String bfStr    = juce::String(blockFrames);
    const juce::String statePath = stateFile.getFullPathName(); // empty if no state

    // argv strings must be char* not const char* for posix_spawn.
    std::string a0 = binPath.toStdString();
    std::string a1 = shmName;
    std::string a2 = xmlPath.toStdString();
    std::string a3 = srStr.toStdString();
    std::string a4 = bfStr.toStdString();
    std::string a5 = presetName.toStdString();
    std::string a6 = statePath.toStdString();
    char* argv[] = {
        a0.data(), a1.data(), a2.data(), a3.data(), a4.data(),
        a5.data(), a6.data(), nullptr
    };

    std::fprintf(stderr, "[spawn] calling posix_spawn worker=%s xml=%s\n",
                 a0.c_str(), a2.c_str());
    pid_t pid = -1;
    int rc = ::posix_spawn(&pid, a0.c_str(), &fa, nullptr, argv, environ);
    ::posix_spawn_file_actions_destroy(&fa);
    std::fprintf(stderr, "[spawn] posix_spawn rc=%d pid=%d\n", rc, (int) pid);

    // Parent closes the child-side pipe ends now that they're inherited.
    ::close(e2w[0]);  e2w[0]  = -1;
    ::close(w2e[1]);  w2e[1]  = -1;
    ::close(e2wc[0]); e2wc[0] = -1;
    ::close(w2ec[1]); w2ec[1] = -1;

    if (rc != 0) {
        errOut = "posix_spawn failed: " + juce::String(std::strerror(rc));
        ::close(e2w[1]);
        ::close(w2e[0]);
        ::close(e2wc[1]);
        ::close(w2ec[0]);
        ::munmap(mem, kSharedBlockBytes);
        ::shm_unlink(shmName);
        return nullptr;
    }

    // Default 2-in / 2-out. If the plugin reports different bus counts we
    // could query and adjust, but every non-multichannel plugin fits here.
    const int inCh  = 2;
    const int outCh = 2;

    auto proxy = std::make_unique<PluginProxy>(
        shm, std::string(shmName),
        e2w[1], w2e[0],
        e2wc[1], w2ec[0],
        pid, desc.name,
        inCh, outCh);
    // Reader thread must start before any queryParams call; do it here so
    // the caller can immediately hit synchronous request endpoints.
    proxy->startEventReader();
    std::fprintf(stderr, "[spawn] event reader started, about to queryParams\n");
    auto params = proxy->queryParams(500);
    proxy->setCachedParams(params);
    std::fprintf(stderr, "[spawn] queryParams returned, exiting spawn cleanly\n");
    return proxy;
}

} // namespace nasty::sandbox
