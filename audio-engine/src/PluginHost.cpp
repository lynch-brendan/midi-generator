#include "PluginHost.h"
#include "GmSynth.h"
#include "SampleDrum.h"
#include <iostream>
#include <cstdio>

#if __APPLE__
namespace nasty {
    void makeWindowNonActivating(void* nativeViewHandle);
    void setWindowFloating(void* nativeViewHandle, bool floating);
    bool isEngineAppActive();
}
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

// Stereo passthrough processor used for mixer insert BUSES. Multiple source
// channels connect audio into a bus's input; the bus runs its own effect
// chain on the summed audio and sends the result to master (or another bus).
// Defined at namespace scope, NOT locally inside createBusChannel — a local
// class type cannot be safely handed to std::make_unique across the JUCE
// audio graph, and doing so was crashing the render-sequence builder.
class BusPassthrough : public juce::AudioProcessor {
public:
    BusPassthrough() : juce::AudioProcessor(BusesProperties()
        .withInput("In",  juce::AudioChannelSet::stereo(), true)
        .withOutput("Out", juce::AudioChannelSet::stereo(), true)) {}
    const juce::String getName() const override    { return "NastyBus"; }
    void prepareToPlay(double, int) override        {}
    void releaseResources() override                {}
    bool acceptsMidi() const override               { return false; }
    bool producesMidi() const override              { return false; }
    double getTailLengthSeconds() const override    { return 0.0; }
    // Passthrough: explicitly copy input bus → output bus in case JUCE's
    // graph doesn't use in-place processing for this node (empty processBlock
    // was silencing audio when this bus sat between the drums and the
    // output).
    void processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer&) override {
        auto inBus  = getBusBuffer(buf, true,  0);
        auto outBus = getBusBuffer(buf, false, 0);
        const int n = buf.getNumSamples();
        const int chs = juce::jmin(inBus.getNumChannels(), outBus.getNumChannels());
        for (int c = 0; c < chs; ++c)
            if (outBus.getReadPointer(c) != inBus.getReadPointer(c))
                outBus.copyFrom(c, 0, inBus, c, 0, n);
    }
    void processBlock(juce::AudioBuffer<double>& buf, juce::MidiBuffer&) override {
        auto inBus  = getBusBuffer(buf, true,  0);
        auto outBus = getBusBuffer(buf, false, 0);
        const int n = buf.getNumSamples();
        const int chs = juce::jmin(inBus.getNumChannels(), outBus.getNumChannels());
        for (int c = 0; c < chs; ++c)
            if (outBus.getReadPointer(c) != inBus.getReadPointer(c))
                outBus.copyFrom(c, 0, inBus, c, 0, n);
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

// Minimal play head so tempo-syncing plugins have a valid host tempo to read.
// Without this, VST3s read 0/uninitialised BPM and behave weirdly (Serato
// Sample slicers freeze at ~1 BPM). AU wrappers often fall back to 120 which
// masks the bug, but VST3 does not — hence the format-dependent symptom.
class NastyPlayHead : public juce::AudioPlayHead {
public:
    juce::Optional<PositionInfo> getPosition() const override {
        PositionInfo info;
        info.setBpm(120.0);
        info.setTimeSignature(TimeSignature{4, 4});
        info.setIsPlaying(false);
        info.setIsRecording(false);
        info.setIsLooping(false);
        info.setTimeInSamples(0);
        info.setTimeInSeconds(0.0);
        info.setPpqPosition(0.0);
        info.setPpqPositionOfLastBarStart(0.0);
        return info;
    }
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

    // Publish a fixed 120 BPM play head so tempo-syncing plugins have valid
    // host transport info. AudioProcessorGraph forwards it to child nodes.
    playHead = std::make_unique<NastyPlayHead>();
    graph.setPlayHead(playHead.get());

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
    // deadMansFile: if a plugin crashes mid-scan, its path gets written here
    // BEFORE the crash. Next scan skips anything already in the file — so one
    // bad plugin can never take down the whole engine on boot again.
    auto supportDir = juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory)
        .getChildFile("nasty");
    supportDir.createDirectory();
    auto deadMans = supportDir.getChildFile("scan-crashes.txt");

    for (int i = 0; i < formatManager.getNumFormats(); ++i) {
        auto* format = formatManager.getFormat(i);
        auto searchPaths = format->getDefaultLocationsToSearch();

        // Also scan a bundled-with-app instruments folder if the parent
        // process points us at one (via NASTY_INSTRUMENTS_PATH). Lets Nasty
        // ship Sfizz + curated sample libraries in the .dmg with zero
        // install work for the user.
        if (const char* extra = std::getenv("NASTY_INSTRUMENTS_PATH")) {
            juce::File extraDir(juce::String::fromUTF8(extra));
            if (extraDir.isDirectory()) {
                searchPaths.add(extraDir);
            }
        }

        juce::PluginDirectoryScanner scanner(
            knownPlugins, *format, searchPaths,
            /*recursive*/ true, deadMans);

        juce::String nameBeingScanned;
        int idx = 0, total = (int)knownPlugins.getNumTypes();
        while (scanner.scanNextFile(true, nameBeingScanned)) {
            if (onProgress) onProgress(nameBeingScanned, ++idx, total);
        }
    }
}

bool PluginHost::loadPluginCache(const juce::File& cacheFile) {
    if (!cacheFile.existsAsFile()) return false;
    auto xml = juce::XmlDocument::parse(cacheFile);
    if (!xml) return false;
    knownPlugins.recreateFromXml(*xml);
    return knownPlugins.getNumTypes() > 0;
}

void PluginHost::savePluginCache(const juce::File& cacheFile) const {
    cacheFile.getParentDirectory().createDirectory();
    auto xml = knownPlugins.createXml();
    if (xml) xml->writeTo(cacheFile);
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

    // OUTPUT-ONLY. If we open the input side of a Bluetooth headset, macOS
    // switches it into hands-free (HFP) mode — 24kHz mono — which wrecks
    // music playback. Explicitly disable input to keep AirPods in A2DP.
    juce::AudioDeviceManager::AudioDeviceSetup setup;
    setup.inputDeviceName = "";
    setup.useDefaultInputChannels = false;
    setup.inputChannels.clear();
    setup.useDefaultOutputChannels = true;
    juce::String err = deviceManager.initialise(
        /*numInputs*/  0,
        /*numOutputs*/ 2,
        /*savedState*/ nullptr,
        /*selectDefaultDevice*/ true,
        /*preferredDefault*/ juce::String(),
        &setup);
    if (err.isNotEmpty()) {
        std::cerr << "[PluginHost] audio init failed: " << err << std::endl;
        return;
    }

    // Trust the system default. User picks what they want from the dropdown.
    // We only WARN (via the sample-rate readout in the toolbar) if the rate
    // looks too low to play music — we never switch silently.

    // If the device came up at a music-hostile rate (Bluetooth hands-free
    // mode = 16/24kHz), try to force it back to 48000. If CoreAudio can't
    // honor the request, the front end's warning modal fires and the user
    // picks a different device from the Out dropdown.
    if (auto* dev = deviceManager.getCurrentAudioDevice()) {
        if (dev->getCurrentSampleRate() < 44100.0) {
            juce::AudioDeviceManager::AudioDeviceSetup s;
            deviceManager.getAudioDeviceSetup(s);
            s.sampleRate = 48000.0;
            deviceManager.setAudioDeviceSetup(s, true);
        }
    }

    if (!deviceManager.getCurrentAudioDevice()) {
        std::cerr << "[PluginHost] no current audio device after init" << std::endl;
    }
    setProcessor(&graph);
    deviceManager.addAudioCallback(this);
    deviceManager.addMidiInputDeviceCallback({}, this);
    // Listen for device changes so we can reconnect when macOS wakes from
    // sleep, or the user unplugs and replugs an interface. Without this the
    // engine holds a stale device handle and stays silent after wake.
    deviceManager.addChangeListener(this);
    audioRunning = true;
}

void PluginHost::changeListenerCallback(juce::ChangeBroadcaster* source) {
    if (source != &deviceManager) return;
    // If the current device went away (sleep, unplug), rebind to defaults so
    // audio comes back automatically instead of staying silent.
    auto* currentDevice = deviceManager.getCurrentAudioDevice();
    if (currentDevice && currentDevice->isOpen()) return;
    std::cerr << "[PluginHost] audio device changed / lost — reconnecting" << std::endl;
    deviceManager.removeAudioCallback(this);
    deviceManager.initialiseWithDefaultDevices(0, 2);
    deviceManager.addAudioCallback(this);
}

void PluginHost::stopAudio() {
    if (!audioRunning) return;
    deviceManager.removeChangeListener(this);
    deviceManager.removeAudioCallback(this);
    deviceManager.removeMidiInputDeviceCallback({}, this);
    setProcessor(nullptr);
    audioRunning = false;
}

juce::String PluginHost::loadPlugin(const juce::String& channelId,
                                    const juce::String& pluginId,
                                    const juce::String& base64State) {
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

    // Publish host tempo to the plugin directly (not all wrappers pick it up
    // through the graph forwarding path — VST3 in particular reads from the
    // processor's playhead at first processBlock).
    instance->setPlayHead(playHead.get());

    // Apply previously-saved plugin state (Serato's loaded sample, Serum
    // patch, etc.). Failure is silent — a corrupt blob shouldn't block load.
    if (base64State.isNotEmpty()) {
        juce::MemoryOutputStream decoded;
        if (juce::Base64::convertFromBase64(decoded, base64State) && decoded.getDataSize() > 0) {
            instance->setStateInformation(decoded.getData(), (int) decoded.getDataSize());
        }
    }

    unloadPlugin(channelId); // replace if exists

    auto injectorNode = graph.addNode(std::make_unique<MidiInjector>());
    auto pluginNode   = graph.addNode(std::move(instance));

    // MIDI: injector → plugin.
    graph.addConnection({{injectorNode->nodeID, Graph::midiChannelIndex},
                         {pluginNode->nodeID,   Graph::midiChannelIndex}});

    {
        std::lock_guard<std::mutex> lock(mutex);
        ChannelSlot slot{ pluginNode->nodeID, injectorNode->nodeID, 1, {}, {}, false };
        channels[channelId] = slot;
        rewireChannelUnlocked(channels[channelId]); // instrument → output
    }
    return {};
}

juce::String PluginHost::addGmChannel(const juce::String& channelId,
                                      int gmProgram,
                                      const juce::String& sf2Path) {
    startAudio();

    auto gm = std::make_unique<GmSynth>();
    if (!gm->loadSoundFont(sf2Path)) {
        std::cerr << "[PluginHost] SF2 load failed: " << sf2Path << std::endl;
        return "Failed to load SoundFont: " + sf2Path;
    }
    gm->setProgram(gmProgram);

    unloadPlugin(channelId); // replace if exists

    auto injectorNode = graph.addNode(std::make_unique<MidiInjector>());
    auto gmNode       = graph.addNode(std::move(gm));

    // MIDI: injector → gm.
    graph.addConnection({{injectorNode->nodeID, Graph::midiChannelIndex},
                         {gmNode->nodeID,       Graph::midiChannelIndex}});

    {
        std::lock_guard<std::mutex> lock(mutex);
        ChannelSlot slot{ gmNode->nodeID, injectorNode->nodeID, 1, {}, {}, false };
        channels[channelId] = slot;
        rewireChannelUnlocked(channels[channelId]); // gm → output
    }
    return {};
}

juce::String PluginHost::addDrumChannel(const juce::String& channelId,
                                        const juce::String& samplePath,
                                        int rootNote) {
    std::cerr << "[PluginHost] add_drum ch=" << channelId
              << " sample=" << samplePath << std::endl;
    startAudio();

    auto drum = std::make_unique<SampleDrum>();
    if (!drum->loadSample(samplePath, rootNote)) {
        std::cerr << "[PluginHost] drum sample load failed: " << samplePath << std::endl;
        return "Failed to load sample: " + samplePath;
    }

    unloadPlugin(channelId);

    auto injectorNode = graph.addNode(std::make_unique<MidiInjector>());
    auto drumNode     = graph.addNode(std::move(drum));

    // MIDI: injector → drum.
    graph.addConnection({{injectorNode->nodeID, Graph::midiChannelIndex},
                         {drumNode->nodeID,     Graph::midiChannelIndex}});

    {
        std::lock_guard<std::mutex> lock(mutex);
        ChannelSlot slot{ drumNode->nodeID, injectorNode->nodeID, 1, {}, {}, false };
        channels[channelId] = slot;
        rewireChannelUnlocked(channels[channelId]);
    }
    return {};
}

void PluginHost::setGmProgram(const juce::String& channelId, int gmProgram) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto node = graph.getNodeForId(it->second.pluginNodeId);
    if (!node) return;
    if (auto* gm = dynamic_cast<GmSynth*>(node->getProcessor())) {
        gm->setProgram(gmProgram);
    }
}

void PluginHost::unloadPlugin(const juce::String& channelId) {
    // Close the editor window first (on message thread) so its held editor
    // pointer doesn't dangle when we drop the plugin node below.
    hidePluginUI(channelId);

    // Also close any effect editor windows on this channel and drop their nodes.
    std::vector<juce::String> effectSlotIds;
    {
        std::lock_guard<std::mutex> lock(mutex);
        auto it = channels.find(channelId);
        if (it != channels.end()) {
            for (const auto& e : it->second.effects) effectSlotIds.push_back(e.slotId);
        }
    }
    for (const auto& sid : effectSlotIds) hideEffectUI(channelId, sid);

    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    for (const auto& e : it->second.effects) graph.removeNode(e.nodeId);
    graph.removeNode(it->second.pluginNodeId);
    graph.removeNode(it->second.injectorNodeId);
    channels.erase(it);
}

// Rebuild the audio graph for one channel. Called after any effect-chain
// mutation (add/remove/reorder/bypass) or after routing changes.  Must be
// called with `mutex` held.
//
// Chain shape: source → eff[0] → eff[1] → ... → target.  Bypassed effects
// are skipped (the audio flows around them). Target = master out by default,
// or the input node of another channel (bus routing) if targetChannelId is
// set.
void PluginHost::rewireChannelUnlocked(ChannelSlot& slot) {
    auto outNode = graph.getNodeForId(Graph::NodeID(2));
    if (!outNode) return;

    // Pause the audio thread while we mutate the graph — otherwise the
    // render-sequence rebuild races with our add/remove calls and can
    // dereference a Node whose processor hasn't been wired in yet (SIGSEGV).
    graph.suspendProcessing(true);

    // Snapshot connections first — removing while iterating the live list
    // would invalidate our iterator on some JUCE versions.
    auto conns = graph.getConnections();

    auto isChannelNode = [&](Graph::NodeID nid) {
        if (nid == slot.pluginNodeId) return true;
        for (const auto& e : slot.effects) if (nid == e.nodeId) return true;
        return false;
    };

    // Resolve target. Empty targetChannelId means route to master output
    // (which is either the master_bus insert if one exists, or the raw
    // audio output node). Non-empty means route to that channel/bus.
    Graph::NodeID targetNodeId = outNode->nodeID;
    if (slot.targetChannelId.isNotEmpty()) {
        auto it = channels.find(slot.targetChannelId);
        if (it != channels.end()) targetNodeId = it->second.pluginNodeId;
    } else {
        // Route through master_bus if it exists, otherwise straight to out.
        auto masterIt = channels.find("master_bus");
        if (masterIt != channels.end() && &slot != &masterIt->second) {
            targetNodeId = masterIt->second.pluginNodeId;
        }
    }

    for (const auto& c : conns) {
        // Only tear down the OUTPUT side of this channel's chain — where the
        // source is one of this channel's nodes and destination is either
        // another of this channel's nodes, or the master output, or any
        // OTHER channel's input (in case we're changing routing target).
        if (c.source.channelIndex == Graph::midiChannelIndex) continue;
        if (!isChannelNode(c.source.nodeID)) continue;
        graph.removeConnection(c);
    }

    // Reconnect: source (instrument or bus input) → each active effect → target.
    Graph::NodeID prev = slot.pluginNodeId;
    for (auto& e : slot.effects) {
        if (e.bypassed) continue;
        for (int ch = 0; ch < 2; ++ch) {
            graph.addConnection({{prev, ch}, {e.nodeId, ch}});
        }
        prev = e.nodeId;
    }
    for (int ch = 0; ch < 2; ++ch) {
        graph.addConnection({{prev, ch}, {targetNodeId, ch}});
    }

    graph.suspendProcessing(false);
}

juce::String PluginHost::createBusChannel(const juce::String& channelId) {
    startAudio();
    auto node = graph.addNode(std::make_unique<BusPassthrough>());

    std::lock_guard<std::mutex> lock(mutex);
    // Replace existing bus with same id (idempotent create).
    auto existing = channels.find(channelId);
    if (existing != channels.end()) {
        for (const auto& e : existing->second.effects) graph.removeNode(e.nodeId);
        graph.removeNode(existing->second.pluginNodeId);
        if (existing->second.injectorNodeId != juce::AudioProcessorGraph::NodeID{})
            graph.removeNode(existing->second.injectorNodeId);
        channels.erase(existing);
    }
    ChannelSlot slot{ node->nodeID, juce::AudioProcessorGraph::NodeID{}, 1, {}, {}, true };
    channels[channelId] = slot;
    rewireChannelUnlocked(channels[channelId]);
    return {};
}

void PluginHost::setChannelTarget(const juce::String& channelId, const juce::String& targetChannelId) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    if (it->second.targetChannelId == targetChannelId) return;
    it->second.targetChannelId = targetChannelId;
    rewireChannelUnlocked(it->second);
}

juce::String PluginHost::addEffect(const juce::String& channelId,
                                   const juce::String& slotId,
                                   const juce::String& pluginId,
                                   const juce::String& base64State) {
    const juce::PluginDescription* desc = nullptr;
    for (const auto& t : knownPlugins.getTypes()) {
        if (t.createIdentifierString() == pluginId) { desc = &t; break; }
    }
    if (!desc) return "Plugin not found: " + pluginId;

    juce::String err;
    auto instance = formatManager.createPluginInstance(
        *desc, graph.getSampleRate(), graph.getBlockSize(), err);
    if (!instance) return err.isNotEmpty() ? err : juce::String("Instantiation failed");
    instance->setPlayHead(playHead.get());

    if (base64State.isNotEmpty()) {
        juce::MemoryOutputStream decoded;
        if (juce::Base64::convertFromBase64(decoded, base64State) && decoded.getDataSize() > 0) {
            instance->setStateInformation(decoded.getData(), (int) decoded.getDataSize());
        }
    }

    auto effectNode = graph.addNode(std::move(instance));

    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) {
        graph.removeNode(effectNode->nodeID);
        return "Channel not found: " + channelId;
    }
    // Replace if a slot with this id already exists (idempotent add).
    for (auto& e : it->second.effects) {
        if (e.slotId == slotId) {
            graph.removeNode(e.nodeId);
            e.nodeId = effectNode->nodeID;
            e.bypassed = false;
            rewireChannelUnlocked(it->second);
            return {};
        }
    }
    it->second.effects.push_back({ slotId, effectNode->nodeID, false });
    rewireChannelUnlocked(it->second);
    return {};
}

void PluginHost::removeEffect(const juce::String& channelId, const juce::String& slotId) {
    hideEffectUI(channelId, slotId);
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    auto& fx = it->second.effects;
    auto found = std::find_if(fx.begin(), fx.end(),
                              [&](const EffectSlot& e) { return e.slotId == slotId; });
    if (found == fx.end()) return;
    graph.removeNode(found->nodeId);
    fx.erase(found);
    rewireChannelUnlocked(it->second);
}

void PluginHost::reorderEffects(const juce::String& channelId, const juce::StringArray& newOrder) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    std::vector<EffectSlot> reordered;
    reordered.reserve(it->second.effects.size());
    for (const auto& sid : newOrder) {
        auto found = std::find_if(it->second.effects.begin(), it->second.effects.end(),
                                  [&](const EffectSlot& e) { return e.slotId == sid; });
        if (found != it->second.effects.end()) reordered.push_back(*found);
    }
    // Keep any slots the front end forgot to include (defensive — order
    // messages can race with adds).
    for (const auto& e : it->second.effects) {
        if (std::find_if(reordered.begin(), reordered.end(),
                         [&](const EffectSlot& r) { return r.slotId == e.slotId; })
            == reordered.end()) {
            reordered.push_back(e);
        }
    }
    it->second.effects = std::move(reordered);
    rewireChannelUnlocked(it->second);
}

void PluginHost::bypassEffect(const juce::String& channelId, const juce::String& slotId, bool bypassed) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) return;
    for (auto& e : it->second.effects) {
        if (e.slotId == slotId) {
            if (e.bypassed == bypassed) return;
            e.bypassed = bypassed;
            rewireChannelUnlocked(it->second);
            return;
        }
    }
}

static juce::String effectKey(const juce::String& channelId, const juce::String& slotId) {
    return channelId + "::" + slotId;
}

void PluginHost::showEffectUI(const juce::String& channelId, const juce::String& slotId) {
    juce::MessageManager::callAsync([this, channelId, slotId]() {
        juce::AudioProcessor* proc = nullptr;
        juce::String title;
        {
            std::lock_guard<std::mutex> lock(mutex);
            auto it = channels.find(channelId);
            if (it == channels.end()) return;
            for (const auto& e : it->second.effects) {
                if (e.slotId == slotId) {
                    if (auto node = graph.getNodeForId(e.nodeId)) {
                        proc = node->getProcessor();
                        if (proc) title = proc->getName();
                    }
                    break;
                }
            }
        }
        if (!proc || !proc->hasEditor()) return;

        auto key = effectKey(channelId, slotId);
        auto existing = effectWindows.find(key);
        if (existing != effectWindows.end() && existing->second) {
            existing->second->setVisible(true);
            existing->second->toFront(true);
            return;
        }

        auto* editor = proc->createEditorAndMakeActive();
        if (!editor) return;

        auto win = std::make_unique<PluginWindow>(
            title, editor,
            [this, channelId, slotId]() { hideEffectUI(channelId, slotId); });

#if __APPLE__
        if (auto* peer = win->getPeer()) makeWindowNonActivating(peer->getNativeHandle());
#endif
        effectWindows[key] = std::move(win);
    });
}

void PluginHost::hideEffectUI(const juce::String& channelId, const juce::String& slotId) {
    juce::MessageManager::callAsync([this, channelId, slotId]() {
        effectWindows.erase(effectKey(channelId, slotId));
    });
}

juce::var PluginHost::snapshotEffectStates() {
    std::lock_guard<std::mutex> lock(mutex);
    auto* root = new juce::DynamicObject();
    for (const auto& [chId, slot] : channels) {
        auto* perChannel = new juce::DynamicObject();
        for (const auto& e : slot.effects) {
            auto node = graph.getNodeForId(e.nodeId);
            if (!node || !node->getProcessor()) continue;
            juce::MemoryBlock state;
            node->getProcessor()->getStateInformation(state);
            if (state.getSize() == 0) continue;
            perChannel->setProperty(e.slotId, juce::Base64::toBase64(state.getData(), state.getSize()));
        }
        if (perChannel->getProperties().size() > 0) {
            root->setProperty(chId, juce::var(perChannel));
        } else {
            delete perChannel;
        }
    }
    return juce::var(root);
}

void PluginHost::noteOn(const juce::String& channelId, int pitch, float velocity) {
    std::lock_guard<std::mutex> lock(mutex);
    auto it = channels.find(channelId);
    if (it == channels.end()) {
        std::cerr << "[PluginHost] note_on NO CH: " << channelId << std::endl;
        return;
    }
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

juce::var PluginHost::listAudioDevices() {
    // Make sure the audio subsystem is initialised — otherwise the current
    // device type is null and we'd return an empty output list. Idempotent.
    if (!audioRunning) startAudio();
    auto* obj = new juce::DynamicObject();
    auto* type = deviceManager.getCurrentDeviceTypeObject();
    juce::Array<juce::var> outs;
    if (type) {
        type->scanForDevices();
        for (const auto& n : type->getDeviceNames(false)) outs.add(juce::var(n));
    }
    // If we still don't have any (e.g. no CoreAudio type object yet), walk
    // every registered device type as a fallback.
    if (outs.isEmpty()) {
        for (auto* t : deviceManager.getAvailableDeviceTypes()) {
            if (!t) continue;
            t->scanForDevices();
            for (const auto& n : t->getDeviceNames(false)) outs.add(juce::var(n));
        }
    }
    obj->setProperty("outputs", juce::var(outs));
    juce::AudioDeviceManager::AudioDeviceSetup setup;
    deviceManager.getAudioDeviceSetup(setup);
    obj->setProperty("currentOutput", juce::var(setup.outputDeviceName));
    if (auto* dev = deviceManager.getCurrentAudioDevice()) {
        obj->setProperty("sampleRate", juce::var(dev->getCurrentSampleRate()));
    }
    return juce::var(obj);
}

juce::String PluginHost::setOutputDevice(const juce::String& deviceName) {
    if (!audioRunning) startAudio();
    juce::AudioDeviceManager::AudioDeviceSetup setup;
    deviceManager.getAudioDeviceSetup(setup);
    setup.outputDeviceName = deviceName;
    setup.useDefaultOutputChannels = true;
    auto err = deviceManager.setAudioDeviceSetup(setup, true);
    if (err.isEmpty()) {
        if (auto* dev = deviceManager.getCurrentAudioDevice()) {
            std::cerr << "[PluginHost] switched output to: " << dev->getName() << std::endl;
        }
    } else {
        std::cerr << "[PluginHost] setOutputDevice failed: " << err << std::endl;
    }
    return err;
}

juce::var PluginHost::snapshotPluginStates() {
    std::lock_guard<std::mutex> lock(mutex);
    auto* obj = new juce::DynamicObject();
    for (const auto& [chId, slot] : channels) {
        auto node = graph.getNodeForId(slot.pluginNodeId);
        if (!node || !node->getProcessor()) continue;
        juce::MemoryBlock state;
        node->getProcessor()->getStateInformation(state);
        if (state.getSize() == 0) continue;
        obj->setProperty(chId, juce::Base64::toBase64(state.getData(), state.getSize()));
    }
    return juce::var(obj);
}

void PluginHost::hideAllPluginUIs() {
    juce::MessageManager::callAsync([this]() {
        for (auto& kv : pluginWindows) {
            if (kv.second) kv.second->setVisible(false);
        }
    });
}

void PluginHost::setPluginWindowsFloating(bool floating) {
    juce::MessageManager::callAsync([this, floating]() {
#if __APPLE__
        // If Nasty said "I lost focus" but we (engine) are the ones who took
        // focus (user clicked a plugin's dialog, file picker, etc.), don't
        // lower plugin windows — otherwise they flicker off and on as user
        // interacts with the dialog. Only actually lower when a truly
        // different app (Chrome, Slack) is taking over.
        if (!floating && isEngineAppActive()) return;

        for (auto& kv : pluginWindows) {
            if (!kv.second) continue;
            if (auto* peer = kv.second->getPeer()) {
                setWindowFloating(peer->getNativeHandle(), floating);
            }
        }
#else
        (void) floating;
#endif
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
