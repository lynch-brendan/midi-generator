// Nasty Audio Engine — entry point.
//
// This binary runs as a subprocess of the Electron app. It hosts native
// audio plugins (VST3/AU/CLAP) and speaks to the UI over a local WebSocket.
//
// Status: SCAFFOLDING. Enumerates plugins on startup and sits on the IPC
// socket. Actually loading plugins and rendering audio is the next iteration.

#include <juce_audio_utils/juce_audio_utils.h>
#include <juce_audio_processors/juce_audio_processors.h>

#include "PluginHost.h"
#include "IpcServer.h"

#include <iostream>

int main(int argc, char** argv) {
    juce::ScopedJuceInitialiser_GUI juceInit; // event loop for plugin scanning

    const int port = (argc >= 2) ? std::atoi(argv[1]) : 37173;

    std::cout << "[nasty-audio-engine] starting on ws://127.0.0.1:" << port << std::endl;

    nasty::PluginHost host;
    host.scanDefaultPaths(); // populate available plugins

    nasty::IpcServer server(host, port);
    if (!server.start()) {
        std::cerr << "[nasty-audio-engine] failed to start IPC server" << std::endl;
        return 1;
    }

    std::cout << "[nasty-audio-engine] ready. "
              << host.pluginCount() << " plugins discovered." << std::endl;

    // Block on JUCE's message loop (needed for plugin UIs, timers, etc.)
    juce::MessageManager::getInstance()->runDispatchLoop();
    return 0;
}
