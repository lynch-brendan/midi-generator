#pragma once

// StdioBridge — line-delimited JSON over stdin/stdout to the Electron parent.
// Each direction sends one JSON object per line, no framing beyond newline.

#include <juce_core/juce_core.h>
#include "PluginHost.h"

#include <atomic>
#include <initializer_list>
#include <string>
#include <thread>
#include <utility>

namespace nasty {

class StdioBridge {
public:
    explicit StdioBridge(PluginHost& host);
    ~StdioBridge();

    void startReadThread();
    void stop();

    // Send an event to the UI. Accepts an init list of {key, value} pairs.
    struct KV { const char* key; juce::var value; };
    void sendEvent(std::initializer_list<KV> pairs);

private:
    void handleLine(const std::string& line);
    juce::var handleCommand(const juce::var& msg);

    PluginHost& host;
    std::thread readThread;
    std::atomic<bool> running{false};
};

} // namespace nasty
