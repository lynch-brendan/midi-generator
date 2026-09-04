#include "PluginHost.h"
#include <iostream>

namespace nasty {

using Graph = juce::AudioProcessorGraph;

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

    auto node = graph.addNode(std::move(instance));

    // Connect the plugin to the output. Assume stereo.
    for (int ch = 0; ch < 2; ++ch) {
        graph.addConnection({{node->nodeID, ch}, {graph.getNodeForId(Graph::NodeID(2))->nodeID, ch}});
    }
    // MIDI: route the graph's midi input into this node
    graph.addConnection({{Graph::NodeID(3), Graph::midiChannelIndex},
                         {node->nodeID,      Graph::midiChannelIndex}});

    {
        std::lock_guard<std::mutex> lock(mutex);
        channels[channelId] = { node->nodeID, 1 };
    }
    return {};
}

void PluginHost::unloadPlugin(const juce::String& channelId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    graph.removeNode(it->second.nodeId);
    channels.erase(it);
}

void PluginHost::noteOn(const juce::String& channelId, int pitch, float velocity) {
    (void)channelId; (void)pitch; (void)velocity;
    // TODO: buffer MIDI events and inject them in the audio callback. Doing
    // it outside processBlock requires a lock-free MIDI queue per plugin node.
}

void PluginHost::noteOff(const juce::String& channelId, int pitch) {
    (void)channelId; (void)pitch;
}

void PluginHost::setParam(const juce::String& channelId, int paramIndex, float value01) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    if (auto node = graph.getNodeForId(it->second.nodeId)) {
        auto& params = node->getProcessor()->getParameters();
        if (paramIndex >= 0 && paramIndex < params.size()) {
            params[paramIndex]->setValueNotifyingHost(value01);
        }
    }
}

} // namespace nasty
