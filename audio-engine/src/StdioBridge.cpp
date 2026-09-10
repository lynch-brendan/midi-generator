#include "StdioBridge.h"
#include <iostream>
#include <sstream>

namespace nasty {

StdioBridge::StdioBridge(PluginHost& h) : host(h) {}
StdioBridge::~StdioBridge() { stop(); }

void StdioBridge::PositionBroadcaster::timerCallback() {
    auto& tr = bridge.host.getTransport();
    auto& pp = bridge.host.getPatternPlayer();
    // Emit while playing; also emit on the tick after stop so the UI sees a
    // final "resting" position instead of a stale intermediate value.
    static thread_local bool lastPlaying = false;
    const bool playing = tr.getIsPlaying();
    if (playing || lastPlaying) {
        bridge.sendEvent({
            {"event",           juce::var("transport_position")},
            {"currentSample",   juce::var((double) tr.getCurrentSample())},
            {"sampleRate",      juce::var(tr.getSampleRate())},
            {"isPlaying",       juce::var(playing)},
            // Pattern-loop state — playhead reads position directly, no mod.
            {"patternPosition", juce::var((double) pp.getPositionSample())},
            {"patternLoopSamples", juce::var((double) pp.getLoopLengthSamples())},
        });
    }
    lastPlaying = playing;
}

void StdioBridge::startPositionBroadcaster(int hz) {
    if (!broadcaster) broadcaster = std::make_unique<PositionBroadcaster>(*this);
    broadcaster->startTimerHz(hz);
}

void StdioBridge::stopPositionBroadcaster() {
    if (broadcaster) broadcaster->stopTimer();
}

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
        auto err = host.loadPlugin(msg["channelId"].toString(),
                                   msg["pluginId"].toString(),
                                   msg["state"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event",     err.isEmpty() ? "plugin_loaded" : "error");
        o->setProperty("channelId", msg["channelId"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "add_gm_channel") {
        auto err = host.addGmChannel(msg["channelId"].toString(),
                                     (int) msg["program"],
                                     msg["sf2Path"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event",     err.isEmpty() ? "gm_channel_added" : "error");
        o->setProperty("channelId", msg["channelId"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "add_drum_channel") {
        int rootNote = msg.hasProperty("rootNote") ? (int) msg["rootNote"] : 60;
        auto err = host.addDrumChannel(msg["channelId"].toString(),
                                       msg["samplePath"].toString(),
                                       rootNote);
        auto* o = new juce::DynamicObject();
        o->setProperty("event",     err.isEmpty() ? "drum_channel_added" : "error");
        o->setProperty("channelId", msg["channelId"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "set_gm_program") {
        host.setGmProgram(msg["channelId"].toString(), (int) msg["program"]);
        return {};
    }

    if (cmd == "snapshot_plugin_states") {
        // Snapshot on the message thread — some plugins expect getState there.
        juce::MessageManager::callAsync([this]() {
            auto states = host.snapshotPluginStates();
            sendEvent({
                {"event",  juce::var("plugin_states_snapshot")},
                {"states", states},
            });
        });
        return {};
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

    if (cmd == "nasty_focus") {
        host.setPluginWindowsFloating((bool) msg["focused"]);
        return {};
    }

    if (cmd == "hide_all_plugin_uis") {
        host.hideAllPluginUIs();
        return {};
    }

    if (cmd == "add_effect") {
        auto err = host.addEffect(msg["channelId"].toString(),
                                  msg["slotId"].toString(),
                                  msg["pluginId"].toString(),
                                  msg["state"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event",     err.isEmpty() ? "effect_added" : "error");
        o->setProperty("channelId", msg["channelId"]);
        o->setProperty("slotId",    msg["slotId"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "remove_effect") {
        host.removeEffect(msg["channelId"].toString(), msg["slotId"].toString());
        return {};
    }

    if (cmd == "reorder_effects") {
        juce::StringArray order;
        if (auto* arr = msg["slotIds"].getArray()) {
            for (const auto& v : *arr) order.add(v.toString());
        }
        host.reorderEffects(msg["channelId"].toString(), order);
        return {};
    }

    if (cmd == "bypass_effect") {
        host.bypassEffect(msg["channelId"].toString(),
                          msg["slotId"].toString(),
                          (bool) msg["bypassed"]);
        return {};
    }

    if (cmd == "show_effect_ui") {
        host.showEffectUI(msg["channelId"].toString(), msg["slotId"].toString());
        return {};
    }

    if (cmd == "hide_effect_ui") {
        host.hideEffectUI(msg["channelId"].toString(), msg["slotId"].toString());
        return {};
    }

    if (cmd == "snapshot_effect_states") {
        juce::MessageManager::callAsync([this]() {
            auto states = host.snapshotEffectStates();
            sendEvent({
                {"event",  juce::var("effect_states_snapshot")},
                {"states", states},
            });
        });
        return {};
    }

    if (cmd == "create_bus") {
        auto err = host.createBusChannel(msg["channelId"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event",     err.isEmpty() ? "bus_created" : "error");
        o->setProperty("channelId", msg["channelId"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "set_channel_target") {
        host.setChannelTarget(msg["channelId"].toString(),
                              msg["targetChannelId"].toString());
        return {};
    }

    if (cmd == "transport_play") {
        host.getTransport().play();
        return {};
    }

    if (cmd == "transport_stop") {
        host.getTransport().stop();
        // Flush any notes the pattern walker had already injected but whose
        // note-off hadn't fired yet. Without this, stopping in the middle of
        // a held pattern note leaves the plugin stuck.
        host.panicAllChannels();
        return {};
    }

    if (cmd == "transport_seek") {
        host.getTransport().seek((juce::int64) (double) msg["sample"]);
        return {};
    }

    if (cmd == "transport_set_tempo") {
        host.getTransport().setTempo((double) msg["bpm"]);
        return {};
    }

    if (cmd == "transport_set_loop_length" || cmd == "pattern_set_loop_length") {
        // Routes to the PatternPlayer — the walker + visual playhead read
        // from there. The Transport itself is now purely session time.
        // transport_set_loop_length kept as an alias for the old JS name.
        host.getPatternPlayer().setLoopLengthSamples(
            (juce::int64) (double) msg["samples"]);
        return {};
    }

    if (cmd == "pattern_seek") {
        host.getPatternPlayer().seek((juce::int64) (double) msg["sample"]);
        return {};
    }

    if (cmd == "metronome_set_enabled") {
        host.setMetronomeEnabled((bool) msg["enabled"]);
        return {};
    }

    if (cmd == "pattern_set_note") {
        host.setPatternNote(
            msg["channelId"].toString(),
            msg["noteId"].toString(),
            (int) msg["pitch"],
            (float) (double) msg["velocity"],
            (juce::int64) (double) msg["atSample"],
            (juce::int64) (double) msg["durationSamples"]);
        return {};
    }

    if (cmd == "pattern_clear_note") {
        host.clearPatternNote(msg["channelId"].toString(),
                              msg["noteId"].toString());
        return {};
    }

    if (cmd == "pattern_clear") {
        host.clearPattern(msg["channelId"].toString());
        return {};
    }

    if (cmd == "transport_get") {
        auto& tr = host.getTransport();
        auto& pp = host.getPatternPlayer();
        auto* o = new juce::DynamicObject();
        o->setProperty("event",              "transport_state");
        o->setProperty("currentSample",      (double) tr.getCurrentSample());
        o->setProperty("isPlaying",          tr.getIsPlaying());
        o->setProperty("tempo",              tr.getTempoBpm());
        o->setProperty("sampleRate",         tr.getSampleRate());
        // Pattern-loop state (playhead reads this, not the Transport).
        o->setProperty("patternPosition",    (double) pp.getPositionSample());
        o->setProperty("patternLoopSamples", (double) pp.getLoopLengthSamples());
        return juce::var(o);
    }

    if (cmd == "list_audio_devices") {
        auto* o = new juce::DynamicObject();
        o->setProperty("event",   juce::var("audio_devices"));
        o->setProperty("devices", host.listAudioDevices());
        return juce::var(o);
    }

    if (cmd == "set_output_device") {
        auto err = host.setOutputDevice(msg["name"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event", err.isEmpty() ? juce::var("output_device_set") : juce::var("error"));
        o->setProperty("name",  msg["name"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    auto* o = new juce::DynamicObject();
    o->setProperty("event", "unknown_cmd");
    o->setProperty("cmd", cmd);
    return juce::var(o);
}

} // namespace nasty
