#include "PluginHost.h"

namespace nasty {

PluginHost::PluginHost() {
    formatManager.addDefaultFormats(); // enables VST3 + AudioUnit on macOS
}

PluginHost::~PluginHost() = default;

void PluginHost::scanDefaultPaths() {
    for (int i = 0; i < formatManager.getNumFormats(); ++i) {
        auto* format = formatManager.getFormat(i);
        auto searchPaths = format->getDefaultLocationsToSearch();

        juce::PluginDirectoryScanner scanner(
            knownPlugins, *format, searchPaths,
            /*recursive*/ true, /*deadMansFile*/ juce::File());

        juce::String nameBeingScanned;
        while (scanner.scanNextFile(true, nameBeingScanned)) {
            // Optional: report progress via IPC here.
        }
    }
}

size_t PluginHost::pluginCount() const {
    return (size_t) knownPlugins.getNumTypes();
}

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

std::unique_ptr<juce::AudioPluginInstance>
PluginHost::instantiate(const juce::String& pluginId,
                        double sampleRate,
                        int blockSize,
                        juce::String& outError) {
    for (const auto& t : knownPlugins.getTypes()) {
        if (t.createIdentifierString() == pluginId) {
            return formatManager.createPluginInstance(t, sampleRate, blockSize, outError);
        }
    }
    outError = "Plugin not found: " + pluginId;
    return nullptr;
}

} // namespace nasty
