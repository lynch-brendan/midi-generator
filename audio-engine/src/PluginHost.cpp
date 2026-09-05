#include "PluginHost.h"
#include <iostream>

#if __APPLE__
namespace nasty { void makeWindowNonActivating(void* nativeViewHandle); }
#endif

namespace nasty {

using Graph = juce::AudioProcessorGraph;

// MIDI-only processor sitting in front of each plugin. The UI thread enqueues
// note events into its collector; the audio thread drains them into the
// MidiBuffer that flows to the plugin. Lock-free by construction — that's
// MidiMessageCollector's whole job.
namespace {
class MidiInjector : public juce::AudioProcessor {
public:
    juce::MidiMessageCollector collector;

    MidiInjector() : juce::AudioProcessor(BusesProperties()) {}

    const juce::String getName() const override    { return "MidiInjector"; }
    void prepareToPlay(double sr, int) override    { collector.reset(sr); }
    void releaseResources() override               {}
    bool acceptsMidi() const override              { return true; }
    bool producesMidi() const override             { return true; }
    bool isMidiEffect() const override             { return true; }
    double getTailLengthSeconds() const override   { return 0.0; }

    void processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer& midi) override {
        collector.removeNextBlockOfMessages(midi, buf.getNumSamples());
    }
    void processBlock(juce::AudioBuffer<double>& buf, juce::MidiBuffer& midi) override {
        collector.removeNextBlockOfMessages(midi, buf.getNumSamples());
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
};
} // namespace

// A native window that owns a plugin's AudioProcessorEditor. Deletes itself
// asynchronously when the user clicks the close button so the host can
// forget the map entry on the next message-loop tick (avoiding
// use-after-free from inside closeButtonPressed).
class PluginHost::PluginWindow : public juce::DocumentWindow {
public:
    PluginWindow(const juce::String& title, juce::AudioProcessorEditor* editor,
                 std::function<void()> onClose)
        : DocumentWindow(title, juce::Colour(0xff2b2f36),
                         juce::DocumentWindow::minimiseButton | juce::DocumentWindow::closeButton),
          closeCallback(std::move(onClose)) {
        setUsingNativeTitleBar(true);
        setContentOwned(editor, /*resizeToFit*/ true);
        setResizable(editor->isResizable(), false);
        centreWithSize(getWidth(), getHeight());
        // Float above the DAW window so it stays visible while the user types
        // notes into Nasty (which needs keyboard focus to send MIDI).
        setAlwaysOnTop(true);
        setVisible(true);
        toFront(true);
    }

    void closeButtonPressed() override {
        if (closeCallback) juce::MessageManager::callAsync(closeCallback);
    }

private:
    std::function<void()> closeCallback;
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PluginWindow)
};

PluginHost::PluginHost() {
    juce::addDefaultFormatsToManager(formatManager);

    // Add I/O nodes to the graph (input unused for MVP, output routes to speakers).
    graph.addNode(std::make_unique<Graph::AudioGraphIOProcessor>(
        Graph::AudioGraphIOProcessor::audioInputNode));
    graph.addNode(std::make_unique<Graph::AudioGraphIOProcessor>(
        Graph::AudioGraphIOProcessor::audioOutputNode));
    graph.addNode(std::make_unique<Graph::AudioGraphIOProcessor>(
        Graph::AudioGraphIOProcessor::midiInputNode));
    graph.addNode(std::make_unique<Graph::AudioGraphIOProcessor>(
        Graph::AudioGraphIOProcessor::midiOutputNode));
}

PluginHost::~PluginHost() { stopAudio(); }

void PluginHost::scanDefaultPaths(const ScanProgress& onProgress) {
    for (int i = 0; i < formatManager.getNumFormats(); ++i) {
        auto* format = formatManager.getFormat(i);
        auto searchPaths = format->getDefaultLocationsToSearch();

        juce::PluginDirectoryScanner scanner(
            knownPlugins, *format, searchPaths,
            /*recursive*/ true, /*deadMansFile*/ juce::File());

        juce::String nameBeingScanned;
        int idx = 0, total = (int)knownPlugins.getNumTypes();
        while (scanner.scanNextFile(true, nameBeingScanned)) {
            if (onProgress) onProgress(nameBeingScanned, ++idx, total);
        }
    }
}

size_t PluginHost::pluginCount() const { return (size_t) knownPlugins.getNumTypes(); }

juce::var PluginHost::pluginListAsJson() const {
    juce::Array<juce::var> arr;
    for (const auto& t : knownPlugins.getTypes()) {
        auto* o = new juce::DynamicObject();
        o->setProperty("id",           t.createIdentifierString());
        o->setProperty("name",         t.name);
        o->setProperty("format",       t.pluginFormatName);
        o->setProperty("manufacturer", t.manufacturerName);
        o->setProperty("category",     t.category);
        o->setProperty("isInstrument", t.isInstrument);
        arr.add(juce::var(o));
    }
    return juce::var(arr);
}

void PluginHost::startAudio() {
    if (audioRunning) return;
    juce::String err = deviceManager.initialiseWithDefaultDevices(0, 2);
    if (err.isNotEmpty()) {
        std::cerr << "[PluginHost] audio init failed: " << err << std::endl;
        return;
    }
    setProcessor(&graph);
    deviceManager.addAudioCallback(this);
    deviceManager.addMidiInputDeviceCallback({}, this);
    audioRunning = true;
}

void PluginHost::stopAudio() {
    if (!audioRunning) return;
    deviceManager.removeAudioCallback(this);
    deviceManager.removeMidiInputDeviceCallback({}, this);
    setProcessor(nullptr);
    audioRunning = false;
}

juce::String PluginHost::loadPlugin(const juce::String& channelId, const juce::String& pluginId) {
    startAudio(); // lazy-init audio device on first plugin load

    // Find description
    const juce::PluginDescription* desc = nullptr;
    for (const auto& t : knownPlugins.getTypes()) {
        if (t.createIdentifierString() == pluginId) { desc = &t; break; }
    }
    if (!desc) return "Plugin not found: " + pluginId;

    juce::String err;
    auto instance = formatManager.createPluginInstance(
        *desc, graph.getSampleRate(), graph.getBlockSize(), err);
    if (!instance) return err.isNotEmpty() ? err : juce::String("Instantiation failed");

    unloadPlugin(channelId); // replace if exists

    auto injectorNode = graph.addNode(std::make_unique<MidiInjector>());
    auto pluginNode   = graph.addNode(std::move(instance));

    // Audio: plugin → output (assume stereo).
    for (int ch = 0; ch < 2; ++ch) {
        graph.addConnection({{pluginNode->nodeID, ch},
                             {graph.getNodeForId(Graph::NodeID(2))->nodeID, ch}});
    }
    // MIDI: injector → plugin.
    graph.addConnection({{injectorNode->nodeID, Graph::midiChannelIndex},
                         {pluginNode->nodeID,   Graph::midiChannelIndex}});

    {
        std::lock_guard<std::mutex> lock(mutex);
        channels[channelId] = { pluginNode->nodeID, injectorNode->nodeID, 1 };
    }
    return {};
}

void PluginHost::unloadPlugin(const juce::String& channelId) {
    // Close the editor window first (on message thread) so its held editor
    // pointer doesn't dangle when we drop the plugin node below.
    hidePluginUI(channelId);

    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    graph.removeNode(it->second.pluginNodeId);
    graph.removeNode(it->second.injectorNodeId);
    channels.erase(it);
}

void PluginHost::noteOn(const juce::String& channelId, int pitch, float velocity) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->collector.addMessageToQueue(
            juce::MidiMessage::noteOn(it->second.midiChannel, pitch, velocity));
    }
}

void PluginHost::noteOff(const juce::String& channelId, int pitch) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->collector.addMessageToQueue(
            juce::MidiMessage::noteOff(it->second.midiChannel, pitch));
    }
}

void PluginHost::allNotesOff(const juce::String& channelId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.injectorNodeId);
    if (!node) return;
    if (auto* inj = dynamic_cast<MidiInjector*>(node->getProcessor())) {
        inj->collector.addMessageToQueue(
            juce::MidiMessage::allNotesOff(it->second.midiChannel));
        inj->collector.addMessageToQueue(
            juce::MidiMessage::allSoundOff(it->second.midiChannel));
    }
}

void PluginHost::showPluginUI(const juce::String& channelId) {
    juce::MessageManager::callAsync([this, channelId]() {
        std::cerr << "[PluginHost] show_plugin_ui for channel=" << channelId << std::endl;
        juce::AudioProcessor* proc = nullptr;
        juce::String title;
        {
            std::lock_guard<std::mutex> lock(mutex);
            auto it = channels.find(channelId);
            if (it == channels.end()) {
                std::cerr << "[PluginHost] channel not found in map" << std::endl;
                return;
            }
            if (auto node = graph.getNodeForId(it->second.pluginNodeId)) {
                proc = node->getProcessor();
                if (proc) title = proc->getName();
            }
        }
        if (!proc) { std::cerr << "[PluginHost] no processor" << std::endl; return; }
        if (!proc->hasEditor()) { std::cerr << "[PluginHost] plugin has no editor" << std::endl; return; }

        // Bring existing window to front if already open.
        auto existing = pluginWindows.find(channelId);
        if (existing != pluginWindows.end() && existing->second) {
            existing->second->setVisible(true);
            existing->second->toFront(true);
            return;
        }

        auto* editor = proc->createEditorAndMakeActive();
        if (!editor) return;

        auto win = std::make_unique<PluginWindow>(
            title, editor,
            [this, channelId]() { hidePluginUI(channelId); });

#if __APPLE__
        // Make the plugin window a floating panel that never becomes key —
        // Nasty keeps keyboard focus while the plugin UI stays visible and
        // clickable. This is what modern DAWs (Bitwig etc.) do for
        // out-of-process plugin hosting.
        if (auto* peer = win->getPeer()) {
            makeWindowNonActivating(peer->getNativeHandle());
        }
#endif

        pluginWindows[channelId] = std::move(win);
    });
}

void PluginHost::hidePluginUI(const juce::String& channelId) {
    juce::MessageManager::callAsync([this, channelId]() {
        pluginWindows.erase(channelId);
    });
}

void PluginHost::setParam(const juce::String& channelId, int paramIndex, float value01) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    if (auto node = graph.getNodeForId(it->second.pluginNodeId)) {
        auto& params = node->getProcessor()->getParameters();
        if (paramIndex >= 0 && paramIndex < params.size()) {
            params[paramIndex]->setValueNotifyingHost(value01);
        }
    }
}

} // namespace nasty
