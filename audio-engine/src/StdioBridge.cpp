#include "StdioBridge.h"
#include <iostream>
#include <sstream>

namespace nasty {

StdioBridge::StdioBridge(PluginHost& h) : host(h) {}
StdioBridge::~StdioBridge() { stop(); }

void StdioBridge::sendEvent(std::initializer_list<KV> pairs) {
    auto* o = new juce::DynamicObject();
    for (const auto& kv : pairs) o->setProperty(kv.key, kv.value);
    auto json = juce::JSON::toString(juce::var(o), /*allOnOneLine*/ true);
    // stdout is line-buffered; a newline flushes to Electron.
    std::cout << json.toStdString() << "\n" << std::flush;
}

void StdioBridge::startReadThread() {
    running = true;
    readThread = std::thread([this] {
        std::string line;
        while (running && std::getline(std::cin, line)) {
            if (!line.empty()) handleLine(line);
        }
    });
}

void StdioBridge::stop() {
    running = false;
    if (readThread.joinable()) readThread.join();
}

void StdioBridge::handleLine(const std::string& line) {
    juce::var msg = juce::JSON::parse(juce::String(line));
    if (!msg.isObject()) return;
    auto reply = handleCommand(msg);
    if (!reply.isVoid()) {
        auto json = juce::JSON::toString(reply, /*allOnOneLine*/ true);
        std::cout << json.toStdString() << "\n" << std::flush;
    }
}

juce::var StdioBridge::handleCommand(const juce::var& msg) {
    const auto cmd = msg["cmd"].toString();

    if (cmd == "scan_plugins" || cmd == "list_plugins") {
        auto* o = new juce::DynamicObject();
        o->setProperty("event", "plugin_list");
        o->setProperty("plugins", host.pluginListAsJson());
        return juce::var(o);
    }

    if (cmd == "load_plugin") {
        auto err = host.loadPlugin(msg["channelId"].toString(), msg["pluginId"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event",     err.isEmpty() ? "plugin_loaded" : "error");
        o->setProperty("channelId", msg["channelId"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "unload_plugin") {
        host.unloadPlugin(msg["channelId"].toString());
        return {};
    }

    if (cmd == "note_on") {
        host.noteOn(msg["channelId"].toString(),
                    (int) msg["pitch"], (float) msg["velocity"]);
        return {};
    }

    if (cmd == "note_off") {
        host.noteOff(msg["channelId"].toString(), (int) msg["pitch"]);
        return {};
    }

    if (cmd == "all_notes_off") {
        host.allNotesOff(msg["channelId"].toString());
        return {};
    }

    if (cmd == "show_plugin_ui") {
        host.showPluginUI(msg["channelId"].toString());
        return {};
    }

    if (cmd == "hide_plugin_ui") {
        host.hidePluginUI(msg["channelId"].toString());
        return {};
    }

    if (cmd == "set_param") {
        host.setParam(msg["channelId"].toString(),
                      (int) msg["paramIndex"], (float) msg["value"]);
        return {};
    }

    auto* o = new juce::DynamicObject();
    o->setProperty("event", "unknown_cmd");
    o->setProperty("cmd", cmd);
    return juce::var(o);
}

} // namespace nasty
