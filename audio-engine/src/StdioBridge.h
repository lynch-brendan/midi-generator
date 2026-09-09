#pragma once

// StdioBridge — line-delimited JSON over stdin/stdout to the Electron parent.
// Each direction sends one JSON object per line, no framing beyond newline.

#include <juce_core/juce_core.h>
#include <juce_events/juce_events.h>
#include "PluginHost.h"

#include <atomic>
#include <initializer_list>
#include <memory>
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

    // Start / stop the transport position broadcaster. When running, emits
    // {event:"transport_position", currentSample, sampleRate} at ~60 Hz so
    // the UI can drive its playhead off the engine clock. Cheap enough to
    // leave on always; UI can also ignore events while stopped.
    void startPositionBroadcaster(int hz = 60);
    void stopPositionBroadcaster();

private:
    void handleLine(const std::string& line);
    juce::var handleCommand(const juce::var& msg);

    // Timer that pulses on the JUCE message thread and pushes a
    // transport_position event whenever the transport is playing.
    class PositionBroadcaster : public juce::Timer {
    public:
        explicit PositionBroadcaster(StdioBridge& b) : bridge(b) {}
        void timerCallback() override;
    private:
        StdioBridge& bridge;
    };
    std::unique_ptr<PositionBroadcaster> broadcaster;

    PluginHost& host;
    std::thread readThread;
    std::atomic<bool> running{false};
};

} // namespace nasty
