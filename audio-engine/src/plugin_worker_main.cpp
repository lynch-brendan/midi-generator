// Nasty plugin worker — child process that hosts ONE plugin instance.
//
// Spawned by the main audio engine per loaded VST/AU. Communicates over:
//   * A SharedPluginBlock in POSIX shared memory (audio + MIDI + lifecycle).
//   * Four anonymous pipes inherited via posix_spawn:
//       fd 3: engine → worker audio wake byte
//       fd 4: worker → engine audio wake byte
//       fd 5: engine → worker JSON control (line-delimited)
//       fd 6: worker → engine JSON events  (line-delimited)
//
// Threading:
//   * Main thread: juce::MessageManager dispatch loop. All plugin state
//     mutations (setParam, setCurrentProgram, setStateInformation, editor
//     create/destroy) happen here via callAsync so JUCE's message-thread
//     contract is honoured.
//   * Audio thread: blocks on fd 3 wake, runs processBlock, writes output,
//     wakes engine on fd 4. Doesn't touch anything that isn't real-time
//     safe on the plugin.
//   * Control thread: blocks on fd 5, parses JSON lines, callAsyncs the
//     handler onto the message thread.
//
// If we crash, the OS closes our pipe fds; the engine's next read on fd 4
// or fd 6 returns EOF and the engine flips the channel to "plugin crashed."

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_audio_utils/juce_audio_utils.h>
#include <juce_gui_basics/juce_gui_basics.h>

#include "PluginSandbox.h"

#if __APPLE__
namespace nasty { void setSubprocessAsAgentApp(); }
#endif

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>

namespace nasty::sandbox {

static constexpr int kEngineToWorkerFd     = 3;
static constexpr int kWorkerToEngineFd     = 4;
static constexpr int kEngineControlReadFd  = 5;  // JSON commands in
static constexpr int kWorkerControlWriteFd = 6;  // JSON events out (unused in v1)

// Map an existing shared-memory segment by name.
static SharedPluginBlock* mapShared(const char* shmName) {
    int fd = ::shm_open(shmName, O_RDWR, 0600);
    if (fd < 0) return nullptr;
    void* mem = ::mmap(nullptr, kSharedBlockBytes, PROT_READ | PROT_WRITE,
                       MAP_SHARED, fd, 0);
    ::close(fd);
    if (mem == MAP_FAILED) return nullptr;
    return reinterpret_cast<SharedPluginBlock*>(mem);
}

static bool loadDescriptionFromXml(const juce::File& xmlFile,
                                   juce::PluginDescription& out) {
    if (!xmlFile.existsAsFile()) return false;
    auto xml = juce::XmlDocument::parse(xmlFile);
    if (!xml) return false;
    return out.loadFromXml(*xml);
}

static void notify(int fd) {
    const char b = 1;
    (void) ::write(fd, &b, 1);
}

static bool waitForInputWake(int fd) {
    char b;
    ssize_t r = ::read(fd, &b, 1);
    return r == 1;
}

static void copyMidiIn(const SharedPluginBlock& shm, juce::MidiBuffer& midi) {
    midi.clear();
    const uint32_t n = shm.input_midi_event_count;
    for (uint32_t i = 0; i < n && i < kMaxMidiEvents; ++i) {
        const auto& e = shm.input_midi_events[i];
        if (e.byte_count == 0 || e.byte_count > 3) continue;
        midi.addEvent(juce::MidiMessage(e.bytes, (int) e.byte_count),
                      (int) e.sample_offset);
    }
}

// Fuzzy-match a preset name against a plugin's program list.
static int matchPresetIndex(juce::AudioPluginInstance& plugin,
                            const juce::String& query) {
    if (query.isEmpty()) return -1;
    const int n = plugin.getNumPrograms();
    if (n <= 0) return -1;
    const auto needle = query.toLowerCase();
    int bestIdx = -1;
    int bestLen = -1;
    for (int i = 0; i < n; ++i) {
        const auto name = plugin.getProgramName(i).toLowerCase();
        if (name == needle) return i;
        if (name.contains(needle) && name.length() > bestLen) {
            bestIdx = i;
            bestLen = name.length();
        }
    }
    return bestIdx;
}

// Shim playhead that reads its state from the shared block. Attached to
// the plugin so tempo-synced plugins in the worker see the engine's
// current transport instead of defaults. Written by the proxy on the
// engine side once per processBlock.
class SharedBlockPlayHead : public juce::AudioPlayHead {
public:
    explicit SharedBlockPlayHead(const nasty::sandbox::SharedPluginBlock* shm) : shm_(shm) {}
    juce::Optional<PositionInfo> getPosition() const override {
        PositionInfo info;
        info.setBpm(shm_->ph_bpm.load(std::memory_order_relaxed));
        info.setIsPlaying(shm_->ph_is_playing.load(std::memory_order_relaxed) != 0);
        info.setTimeInSamples(shm_->ph_time_samples.load(std::memory_order_relaxed));
        info.setTimeInSeconds(shm_->ph_time_seconds.load(std::memory_order_relaxed));
        info.setPpqPosition(shm_->ph_ppq_position.load(std::memory_order_relaxed));
        info.setTimeSignature(TimeSignature{4, 4});
        return info;
    }
private:
    const nasty::sandbox::SharedPluginBlock* shm_;
};

// Editor host window. One per worker at most — the plugin only has one
// editor. Owned by the message thread; created and destroyed via
// show_ui/hide_ui control messages.
class PluginEditorWindow : public juce::DocumentWindow {
public:
    PluginEditorWindow(const juce::String& name, juce::AudioProcessorEditor* editor)
        : DocumentWindow(name, juce::Colours::black, DocumentWindow::closeButton) {
        setUsingNativeTitleBar(true);
        setContentOwned(editor, true);
        setResizable(editor && editor->isResizable(), false);
        setAlwaysOnTop(false);
        centreWithSize(getWidth(), getHeight());
        setVisible(true);
        toFront(true);
    }
    void closeButtonPressed() override {
        // Just hide; the control channel can re-show it.
        setVisible(false);
    }
};

// Global plugin + editor. Simplest model — one worker, one plugin, one
// window. Access ONLY from the message thread except where noted.
static std::unique_ptr<juce::AudioPluginInstance> g_plugin;
static std::unique_ptr<PluginEditorWindow> g_editorWindow;

// Write one JSON line to fd 6 (worker → engine control channel). Used for
// request-response replies (params, state) and for informational events.
static void sendEvent(const juce::var& v) {
    auto line = juce::JSON::toString(v, /*allOnOneLine*/ true) + "\n";
    const auto bytes = line.toRawUTF8();
    (void) ::write(kWorkerControlWriteFd, bytes, std::strlen(bytes));
}

// Dispatch a control command onto the message thread — plugin API expects
// most non-audio calls (setValueNotifyingHost, setCurrentProgram, editor
// create/destroy) to run there.
static void handleControlOnMessageThread(const juce::var& msg) {
    if (!g_plugin) return;
    const auto cmd = msg["cmd"].toString();

    if (cmd == "get_state") {
        const int reqId = (int) msg["reqId"];
        juce::MemoryBlock mb;
        g_plugin->getStateInformation(mb);
        juce::String b64 = mb.getSize() > 0
            ? juce::Base64::toBase64(mb.getData(), mb.getSize())
            : juce::String();
        auto* resp = new juce::DynamicObject();
        resp->setProperty("event",  juce::var("state"));
        resp->setProperty("reqId",  juce::var(reqId));
        resp->setProperty("base64", juce::var(b64));
        sendEvent(juce::var(resp));
        return;
    }

    if (cmd == "get_params") {
        const int reqId = (int) msg["reqId"];
        juce::Array<juce::var> arr;
        const auto& params = g_plugin->getParameters();
        for (int i = 0; i < params.size(); ++i) {
            auto* p = params[i];
            if (!p) continue;
            auto* o = new juce::DynamicObject();
            o->setProperty("index", i);
            o->setProperty("name",  p->getName(48));
            o->setProperty("value", p->getValue());
            arr.add(juce::var(o));
        }
        auto* resp = new juce::DynamicObject();
        resp->setProperty("event",  juce::var("params"));
        resp->setProperty("reqId",  juce::var(reqId));
        resp->setProperty("params", juce::var(arr));
        sendEvent(juce::var(resp));
        return;
    }

    if (cmd == "set_param") {
        const int idx = (int) msg["index"];
        const float v = (float) (double) msg["value"];
        const auto& params = g_plugin->getParameters();
        if (idx >= 0 && idx < params.size()) {
            if (auto* p = params[idx]) p->setValueNotifyingHost(v);
        }
    }
    else if (cmd == "set_program") {
        g_plugin->setCurrentProgram((int) msg["index"]);
    }
    else if (cmd == "set_preset_by_name") {
        const int idx = matchPresetIndex(*g_plugin, msg["name"].toString());
        if (idx >= 0) g_plugin->setCurrentProgram(idx);
    }
    else if (cmd == "show_ui") {
        if (g_editorWindow) {
            g_editorWindow->setVisible(true);
            g_editorWindow->toFront(true);
        } else if (auto* ed = g_plugin->createEditorIfNeeded()) {
            g_editorWindow.reset(new PluginEditorWindow(g_plugin->getName(), ed));
        }
    }
    else if (cmd == "hide_ui") {
        if (g_editorWindow) g_editorWindow->setVisible(false);
    }
    else if (cmd == "shutdown") {
        g_editorWindow.reset();
        juce::MessageManager::getInstance()->stopDispatchLoop();
    }
}

// Control-channel reader thread. Blocks on fd 5, parses JSON lines,
// dispatches to message thread.
static void runControlLoop(int fd) {
    juce::String buf;
    char chunk[1024];
    while (true) {
        ssize_t r = ::read(fd, chunk, sizeof(chunk));
        if (r <= 0) break; // engine closed pipe → shutdown
        buf += juce::String::fromUTF8(chunk, (int) r);
        for (;;) {
            const int nl = buf.indexOfChar('\n');
            if (nl < 0) break;
            juce::String line = buf.substring(0, nl);
            buf = buf.substring(nl + 1);
            juce::var msg = juce::JSON::parse(line);
            if (!msg.isObject()) continue;
            juce::MessageManager::callAsync([msg]() {
                handleControlOnMessageThread(msg);
            });
        }
    }
    // Engine dropped the control pipe — signal shutdown to the message thread.
    juce::MessageManager::callAsync([]() {
        if (g_editorWindow) g_editorWindow.reset();
        juce::MessageManager::getInstance()->stopDispatchLoop();
    });
}

// Point a JUCE AudioBuffer at the shared-memory audio region.
static juce::AudioBuffer<float> viewShmAudio(float* base,
                                             int numChannels,
                                             int numFrames) {
    thread_local float* channelPointers[kMaxChannels];
    for (int c = 0; c < numChannels && c < (int) kMaxChannels; ++c) {
        channelPointers[c] = base + c * (size_t) kMaxBlockFrames;
    }
    return juce::AudioBuffer<float>(channelPointers, numChannels, numFrames);
}

// Audio-thread loop. Blocks on fd 3 wake, runs processBlock, writes SHM.
static void runAudioLoop(SharedPluginBlock* shm) {
    juce::MidiBuffer midi;
    uint64_t lastInputSeq = 0;
    uint64_t buffersProcessed = 0;
    std::fprintf(stderr, "[worker %d] audio loop starting\n", (int) getpid());

    while (true) {
        if (!waitForInputWake(kEngineToWorkerFd)) {
            std::fprintf(stderr, "[worker %d] audio wake pipe closed, exiting\n", (int) getpid());
            break;
        }
        const uint64_t seq = shm->input_seq.load(std::memory_order_acquire);
        if (seq == lastInputSeq) continue;
        lastInputSeq = seq;

        if (!g_plugin) {
            // Not ready yet (message thread hasn't set up plugin) — echo
            // zero. Should be very brief at startup.
            std::memset(shm->output_audio, 0, sizeof(shm->output_audio));
            shm->output_seq.store(seq, std::memory_order_release);
            notify(kWorkerToEngineFd);
            continue;
        }

        const int nInCh  = (int) shm->num_input_channels.load(std::memory_order_relaxed);
        const int nOutCh = (int) shm->num_output_channels.load(std::memory_order_relaxed);
        const int frames = (int) shm->block_frames.load(std::memory_order_relaxed);
        const int nBufCh = std::max(nInCh, nOutCh);

        copyMidiIn(*shm, midi);
        auto workBuf = viewShmAudio(shm->input_audio, nBufCh, frames);
        g_plugin->processBlock(workBuf, midi);

        for (int c = 0; c < nOutCh && c < (int) kMaxChannels; ++c) {
            std::memcpy(shm->output_audio + c * (size_t) kMaxBlockFrames,
                        workBuf.getReadPointer(c),
                        (size_t) frames * sizeof(float));
        }
        shm->output_seq.store(seq, std::memory_order_release);
        notify(kWorkerToEngineFd);
        if (buffersProcessed == 0 || buffersProcessed == 100 || buffersProcessed == 1000) {
            std::fprintf(stderr, "[worker %d] processed buffer #%llu (frames=%d nMidi=%u)\n",
                         (int) getpid(), (unsigned long long) buffersProcessed,
                         frames, (unsigned) midi.getNumEvents());
        }
        ++buffersProcessed;
    }
    // Engine closed the audio pipe — bring down the message thread too.
    juce::MessageManager::callAsync([]() {
        if (g_editorWindow) g_editorWindow.reset();
        juce::MessageManager::getInstance()->stopDispatchLoop();
    });
}

} // namespace nasty::sandbox

int main(int argc, char** argv) {
    using namespace nasty::sandbox;

    if (argc < 5) {
        std::fprintf(stderr,
            "[worker] usage: %s <shm_name> <plugin_desc_xml> <sample_rate> <block_frames> [preset_name] [state_file]\n",
            argv[0]);
        return 2;
    }
    const char* shmName        = argv[1];
    const char* xmlPath        = argv[2];
    const double sampleRate    = std::atof(argv[3]);
    const int blockFrames      = std::atoi(argv[4]);
    const char* presetName     = (argc > 5) ? argv[5] : "";
    const char* stateFilePath  = (argc > 6) ? argv[6] : "";

    juce::ScopedJuceInitialiser_GUI juceInit;
#if __APPLE__
    // Same trick the main engine uses: mark the process as an accessory/agent
    // app so it can own NSWindows (plugin GUIs) without stealing focus or
    // showing a dock icon. Without this, DocumentWindow::setVisible(true)
    // does nothing because the child process has no NSApp activation policy.
    nasty::setSubprocessAsAgentApp();
#endif

    SharedPluginBlock* shm = mapShared(shmName);
    if (!shm) return 3;
    std::fprintf(stderr, "[worker %d] mapped shm=%s\n", (int) getpid(), shmName);

    juce::AudioPluginFormatManager formatManager;
    juce::addDefaultFormatsToManager(formatManager);

    juce::PluginDescription desc;
    if (!loadDescriptionFromXml(juce::File(xmlPath), desc)) return 4;

    juce::String err;
    auto instance = formatManager.createPluginInstance(
        desc, sampleRate, blockFrames, err);
    if (!instance) {
        std::fprintf(stderr, "[worker] createPluginInstance failed: %s\n",
                     err.toRawUTF8());
        return 5;
    }
    instance->prepareToPlay(sampleRate, blockFrames);

    // Attach the SHM-backed playhead so tempo-syncing plugins see the
    // engine's transport (BPM, isPlaying, ppq) even though they live in
    // this child process. Playhead outlives the plugin (owned by main).
    static auto shimHead = std::make_unique<SharedBlockPlayHead>(shm);
    instance->setPlayHead(shimHead.get());

    if (stateFilePath[0] != '\0') {
        juce::File sf(stateFilePath);
        if (sf.existsAsFile()) {
            juce::MemoryBlock mb;
            if (sf.loadFileAsData(mb) && mb.getSize() > 0) {
                instance->setStateInformation(mb.getData(), (int) mb.getSize());
            }
        }
    }
    if (presetName[0] != '\0') {
        const int idx = matchPresetIndex(*instance, juce::String::fromUTF8(presetName));
        if (idx >= 0) instance->setCurrentProgram(idx);
    }

    // Publish the ready plugin to the shared globals AFTER prepareToPlay so
    // the audio thread won't call processBlock on a half-initialised plugin.
    g_plugin = std::move(instance);

    // Ready line goes over the worker → engine control pipe (fd 6) so the
    // engine can route it without it landing in Electron's stdout.
    {
        char line[256];
        std::snprintf(line, sizeof(line),
            "{\"event\":\"worker_ready\",\"plugin\":\"%s\"}\n",
            desc.name.toRawUTF8());
        (void) ::write(kWorkerControlWriteFd, line, std::strlen(line));
    }

    std::thread controlThread([]() { runControlLoop(kEngineControlReadFd); });
    std::thread audioThread  ([shm]() { runAudioLoop(shm); });

    // Main thread runs the JUCE message loop for GUI + callAsync dispatch.
    // Blocks until stopDispatchLoop() is called (from either the audio or
    // control thread on pipe close, or a shutdown control message).
    juce::MessageManager::getInstance()->runDispatchLoop();

    // Tear down plugin from the message thread before the threads exit.
    if (g_plugin) {
        g_plugin->releaseResources();
        g_plugin.reset();
    }
    g_editorWindow.reset();

    // Both threads will exit on pipe close; join them.
    if (audioThread.joinable())   audioThread.join();
    if (controlThread.joinable()) controlThread.join();

    shm->worker_alive.store(0, std::memory_order_release);
    return 0;
}
