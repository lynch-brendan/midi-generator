#include "IpcServer.h"
#include <iostream>

namespace nasty {

IpcServer::IpcServer(PluginHost& h, int p) : host(h), port(p) {}
IpcServer::~IpcServer() { stop(); }

bool IpcServer::start() {
    // TODO: bring in a real WebSocket library and bind on 127.0.0.1:port.
    // For MVP, print that we would have started.
    std::cout << "[IpcServer] (stub) would listen on 127.0.0.1:" << port << std::endl;
    return true;
}

void IpcServer::stop() {
    // TODO: close all clients, shut down server.
}

juce::var IpcServer::handleMessage(const juce::var& msg) {
    if (!msg.isObject()) return {};
    const auto cmd = msg["cmd"].toString();

    if (cmd == "scan_plugins") {
        auto* o = new juce::DynamicObject();
        o->setProperty("event",   "plugin_list");
        o->setProperty("plugins", host.pluginListAsJson());
        return juce::var(o);
    }

    if (cmd == "load_plugin") {
        // TODO: instantiate, add to AudioProcessorGraph, respond with plugin_loaded
        auto* o = new juce::DynamicObject();
        o->setProperty("event", "not_implemented");
        o->setProperty("cmd",   cmd);
        return juce::var(o);
    }

    if (cmd == "note_on" || cmd == "note_off" || cmd == "set_param" || cmd == "transport") {
        // TODO: forward to the appropriate plugin instance / audio graph.
        return {};
    }

    auto* o = new juce::DynamicObject();
    o->setProperty("event", "unknown_cmd");
    o->setProperty("cmd",   cmd);
    return juce::var(o);
}

} // namespace nasty
