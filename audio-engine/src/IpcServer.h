#pragma once

// IpcServer — WebSocket JSON bridge between Electron and the audio engine.
//
// Status: SCAFFOLDING. Uses JUCE's built-in InterprocessConnection as a
// placeholder for now. Real impl will use a proper WS library (e.g. ixwebsocket).

#include <juce_core/juce_core.h>
#include "PluginHost.h"

namespace nasty {

class IpcServer {
public:
    IpcServer(PluginHost& host, int port);
    ~IpcServer();

    bool start();
    void stop();

    // Handle one JSON message from the UI. Returns a JSON response (may be null).
    juce::var handleMessage(const juce::var& msg);

private:
    PluginHost& host;
    int port;
    // Real WS server object goes here (ixwebsocket / uWebSockets / etc).
};

} // namespace nasty
