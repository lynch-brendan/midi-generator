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

// Commands that mutate the audio graph topology (add/remove nodes,
// add/remove connections, replace processors). Only these need to hold the
// MessageManagerLock — hot-path commands (transport_get every buffer, piano-
// roll edits, set_channel_gain) skip the lock to avoid starving the
// message-thread timer that drives the playhead broadcaster.
static bool commandMutatesGraph(const juce::String& cmd) {
    // NOTE: load_plugin and add_effect intentionally NOT here. They call
    // formatManager.createPluginInstance internally, which needs the message
    // thread to pump (Cocoa callbacks, plugin-internal callAsync). Holding
    // MessageManagerLock across that deadlocks the engine — the plugin
    // instantiation runs, needs a message-thread turn, and can't get one
    // because we're holding it. Those two paths take the lock INTERNALLY,
    // only around the graph mutation itself, after createPluginInstance
    // returns. See PluginHost::loadPlugin / addEffect.
    return cmd == "unload_plugin"
        || cmd == "add_gm_channel"
        || cmd == "add_drum_channel"
        || cmd == "remove_effect"
        || cmd == "reorder_effects"
        || cmd == "bypass_effect"
        || cmd == "set_wet_dry"
        || cmd == "set_channel_pan"
        || cmd == "set_channel_stereo_width"
        || cmd == "set_channel_target"
        || cmd == "create_bus"
        || cmd == "reset_graph"
        || cmd == "show_plugin_ui"
        || cmd == "hide_plugin_ui"
        || cmd == "set_output_device"
        || cmd == "set_input_device"
        || cmd == "create_audio_input_channel"
        || cmd == "set_channel_audio_input"
        || cmd == "add_audio_clip"
        || cmd == "remove_audio_clip"
        || cmd == "set_channel_send"
        || cmd == "remove_channel_send";
}

void StdioBridge::handleLine(const std::string& line) {
    juce::var msg = juce::JSON::parse(juce::String(line));
    if (!msg.isObject()) return;
    const auto cmd = msg["cmd"].toString();
    // Log every command except hot-path noise so we can see what the JS is
    // actually sending. Filter out the ~60Hz position poll and per-note edits.
    if (cmd != "transport_get" && cmd != "pattern_get_position") {
        std::cerr << "[cmd] " << cmd;
        if (msg["channelId"].isString())  std::cerr << " channelId=" << msg["channelId"].toString();
        if (msg["pluginId"].isString())   std::cerr << " pluginId=" << msg["pluginId"].toString();
        if (msg["gmProgram"].isInt())     std::cerr << " gmProgram=" << (int) msg["gmProgram"];
        std::cerr << std::endl;
    }
    juce::var reply;
    if (commandMutatesGraph(cmd)) {
        // Graph mutations race with JUCE's async render-sequence rebuild (also
        // on the message thread) — that's the intermittent nullptr crash in
        // RenderSequenceSignature::getNodeMap. Hold the lock so the updater
        // can't run mid-mutation.
        juce::MessageManagerLock mml;
        if (!mml.lockWasGained()) return;
        reply = handleCommand(msg);
    } else {
        // Hot path: transport, pattern edits, gain, queries. No graph mutation
        // so no lock needed — and holding one here would starve the position
        // broadcaster timer, freezing the playhead.
        reply = handleCommand(msg);
    }
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

    if (cmd == "rescan_plugins") {
        // Runtime re-walk of the VST3/AU search paths + preset cache. Called
        // from the browser dock's Rescan button after the user installs a new
        // plugin. The plugin-cache short-circuits every unchanged file, so a
        // rescan with one new plugin costs ~ one plugin instantiation. Runs
        // on this background stdio thread — safe because createPluginInstance
        // needs the message thread to PUMP, not to be idle.
        auto supportDir = juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory)
            .getChildFile("nasty");
        supportDir.createDirectory();
        auto pluginCacheFile = supportDir.getChildFile("plugin-cache.xml");
        auto presetCacheFile = supportDir.getChildFile("plugin-presets.json");

        host.scanDefaultPaths([this](const juce::String& name, int idx, int total) {
            sendEvent({
                {"event", juce::var("scanning")},
                {"name",  juce::var(name)},
                {"index", juce::var(idx)},
                {"total", juce::var(total)},
            });
        });
        host.savePluginCache(pluginCacheFile);

        host.scanAllPluginPresets([this](const juce::String& name, int idx, int total) {
            sendEvent({
                {"event", juce::var("scanning_presets")},
                {"name",  juce::var(name)},
                {"index", juce::var(idx)},
                {"total", juce::var(total)},
            });
        });
        host.savePresetCache(presetCacheFile);

        auto* o = new juce::DynamicObject();
        o->setProperty("event",   "plugin_list");
        o->setProperty("plugins", host.pluginListAsJson());
        return juce::var(o);
    }

    if (cmd == "load_plugin") {
        auto err = host.loadPlugin(msg["channelId"].toString(),
                                   msg["pluginId"].toString(),
                                   msg["state"].toString(),
                                   msg["presetName"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event",     err.isEmpty() ? "plugin_loaded" : "error");
        o->setProperty("channelId", msg["channelId"]);
        if (err.isNotEmpty()) {
            o->setProperty("error", err);
        } else {
            // Include the fresh-off-the-plugin param list so the UI can
            // stash it on the channel — that's what Claude reads to know
            // what knobs it can turn.
            o->setProperty("params", host.paramsForOwner(msg["channelId"].toString()));
        }
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

    if (cmd == "reset_graph") {
        // Tear down every channel + effect. JS follows up with the usual
        // hydrate sequence (create_bus, load_plugin, add_effect, ...) to
        // rebuild from the loaded song's JSON.
        host.resetGraph();
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

    if (cmd == "program_change") {
        // MIDI Program Change to a plugin. The MIDI channel is optional —
        // defaults to the channel slot's assigned MIDI channel if unset or 0.
        // Used to probe whether a hosted plugin (FL Studio AU + FLEX) will
        // switch presets on program change; if yes, we automate priming
        // the whole preset library via a program-change loop.
        host.sendProgramChange(msg["channelId"].toString(),
                               (int) msg["program"],
                               (int) msg["midiChannel"]);
        return {};
    }

    if (cmd == "control_change") {
        // MIDI Control Change. Same use-case as program_change — some
        // plugins expose preset browsing via MIDI CC (via MIDI Learn) even
        // when they don't respond to program change.
        host.sendControlChange(msg["channelId"].toString(),
                               (int) msg["controller"],
                               (int) msg["value"],
                               (int) msg["midiChannel"]);
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
        // slotId empty targets the channel's main plugin (instrument);
        // non-empty targets a specific effect slot in the FX chain.
        host.setParam(msg["channelId"].toString(),
                      msg["slotId"].toString(),
                      (int) msg["paramIndex"], (float) msg["value"]);
        return {};
    }

    if (cmd == "set_wet_dry") {
        // FLOW-owned wet/dry wrap for an effect slot. Sets wetGain/dryGain
        // on the pair of gain nodes the engine created around the plugin,
        // plugin-agnostic — no plugin param routing required.
        host.setEffectWetDry(msg["channelId"].toString(),
                             msg["slotId"].toString(),
                             (float) msg["value"]);
        return {};
    }

    if (cmd == "set_channel_pan") {
        // -1..+1, equal-power channel-independent pan applied post-gain.
        host.setChannelPan(msg["channelId"].toString(),
                           (float) msg["value"]);
        return {};
    }

    if (cmd == "set_channel_stereo_width") {
        // 0..2, M/S width applied post-gain, pre-pan.
        host.setChannelStereoWidth(msg["channelId"].toString(),
                                   (float) msg["value"]);
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
                                  msg["state"].toString(),
                                  msg["presetName"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event",     err.isEmpty() ? "effect_added" : "error");
        o->setProperty("channelId", msg["channelId"]);
        o->setProperty("slotId",    msg["slotId"]);
        if (err.isNotEmpty()) {
            o->setProperty("error", err);
        } else {
            // Same idea as load_plugin — include the effect's param list.
            o->setProperty("params", host.paramsForOwner(
                msg["channelId"].toString(),
                msg["slotId"].toString()));
        }
        return juce::var(o);
    }

    if (cmd == "get_plugin_params") {
        // On-demand param query. Useful if the UI ever needs to refresh
        // (params can change when a plugin loads a preset internally).
        auto* o = new juce::DynamicObject();
        o->setProperty("event", "plugin_params");
        o->setProperty("channelId", msg["channelId"]);
        o->setProperty("slotId", msg["slotId"]);
        o->setProperty("params", host.paramsForOwner(
            msg["channelId"].toString(),
            msg["slotId"].toString()));
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

    // ---- SONG mode ----
    if (cmd == "transport_set_mode") {
        const auto s = msg["mode"].toString();
        host.getTransport().setMode(
            s == "song" ? Transport::Mode::SONG : Transport::Mode::PAT);
        return {};
    }

    if (cmd == "pattern_set_note_in") {
        host.setPatternNoteIn(
            msg["channelId"].toString(),
            msg["patternId"].toString(),
            msg["noteId"].toString(),
            (int) msg["pitch"],
            (float) (double) msg["velocity"],
            (juce::int64) (double) msg["atSample"],
            (juce::int64) (double) msg["durationSamples"]);
        return {};
    }

    if (cmd == "pattern_clear_note_in") {
        host.clearPatternNoteIn(msg["channelId"].toString(),
                                msg["patternId"].toString(),
                                msg["noteId"].toString());
        return {};
    }

    if (cmd == "pattern_clear_in") {
        host.clearPatternInChannel(msg["channelId"].toString(),
                                   msg["patternId"].toString());
        return {};
    }

    if (cmd == "pattern_clear_all_in_channel") {
        host.clearAllPatternsIn(msg["channelId"].toString());
        return {};
    }

    if (cmd == "set_channel_arrangement") {
        host.setChannelArrangement(msg["channelId"].toString(), msg["clips"]);
        return {};
    }

    if (cmd == "clear_channel_arrangement") {
        host.clearChannelArrangement(msg["channelId"].toString());
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

    if (cmd == "set_channel_gain") {
        host.setChannelGain(msg["channelId"].toString(), (float) (double) msg["gain"]);
        return {};
    }

    if (cmd == "set_output_device") {
        auto err = host.setOutputDevice(msg["name"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event", err.isEmpty() ? juce::var("output_device_set") : juce::var("error"));
        o->setProperty("name",  msg["name"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "list_audio_inputs") {
        auto* o = new juce::DynamicObject();
        o->setProperty("event",  juce::var("audio_inputs"));
        auto payload = host.listAudioInputs();
        if (auto* p = payload.getDynamicObject()) {
            for (const auto& kv : p->getProperties()) o->setProperty(kv.name, kv.value);
        }
        return juce::var(o);
    }

    if (cmd == "set_input_device") {
        auto err = host.setInputDevice(msg["name"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event", err.isEmpty() ? juce::var("input_device_set") : juce::var("error"));
        o->setProperty("name",  msg["name"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        // Include the current snapshot so the UI knows how many channels it got.
        auto snap = host.currentInputSnapshot();
        if (auto* s = snap.getDynamicObject()) {
            o->setProperty("inputChannels", s->getProperty("inputChannels"));
        }
        return juce::var(o);
    }

    if (cmd == "create_audio_input_channel") {
        auto err = host.createAudioInputChannel(msg["channelId"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event",     err.isEmpty() ? juce::var("audio_input_channel_created") : juce::var("error"));
        o->setProperty("channelId", msg["channelId"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "set_channel_audio_input") {
        host.setChannelAudioInput(msg["channelId"].toString(), (bool) msg["enabled"]);
        auto* o = new juce::DynamicObject();
        o->setProperty("event",     juce::var("channel_audio_input_set"));
        o->setProperty("channelId", msg["channelId"]);
        o->setProperty("enabled",   msg["enabled"]);
        return juce::var(o);
    }

    if (cmd == "start_recording") {
        juce::String path;
        auto err = host.startRecording(path);
        auto* o = new juce::DynamicObject();
        o->setProperty("event", err.isEmpty() ? juce::var("recording_started") : juce::var("error"));
        o->setProperty("path",  juce::var(path));
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "stop_recording") {
        juce::String path;
        juce::int64 samples = 0;
        auto err = host.stopRecording(path, samples);
        // "not recording" is a benign noop, not an error — JS defensively
        // sends stop_recording on every Stop click as cleanup. Reply with a
        // silent recording_stopped (empty path) instead of surfacing as an
        // engine error the frontend has to filter.
        const bool isNoop = (err == "not recording");
        auto* o = new juce::DynamicObject();
        o->setProperty("event",   (err.isEmpty() || isNoop) ? juce::var("recording_stopped") : juce::var("error"));
        o->setProperty("path",    juce::var(path));
        o->setProperty("samples", juce::var((double) samples));
        if (err.isNotEmpty() && !isNoop) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "start_bounce") {
        juce::String path;
        auto err = host.startBounce(path);
        auto* o = new juce::DynamicObject();
        o->setProperty("event", err.isEmpty() ? juce::var("bounce_started") : juce::var("error"));
        o->setProperty("path",  juce::var(path));
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "stop_bounce") {
        juce::String path;
        juce::int64 samples = 0;
        auto err = host.stopBounce(path, samples);
        const bool isNoop = (err == "not bouncing");
        auto* o = new juce::DynamicObject();
        o->setProperty("event",   (err.isEmpty() || isNoop) ? juce::var("bounce_stopped") : juce::var("error"));
        o->setProperty("path",    juce::var(path));
        o->setProperty("samples", juce::var((double) samples));
        if (err.isNotEmpty() && !isNoop) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "add_audio_clip") {
        auto err = host.addAudioClip(
            msg["clipId"].toString(),
            msg["path"].toString(),
            msg["busId"].toString(),
            (juce::int64) (double) msg["songStartSample"],
            (juce::int64) (double) msg["lengthSamples"]);
        auto* o = new juce::DynamicObject();
        o->setProperty("event",  err.isEmpty() ? juce::var("audio_clip_added") : juce::var("error"));
        o->setProperty("clipId", msg["clipId"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "remove_audio_clip") {
        host.removeAudioClip(msg["clipId"].toString());
        return {};
    }

    if (cmd == "set_audio_clip_position") {
        host.setAudioClipPosition(
            msg["clipId"].toString(),
            (juce::int64) (double) msg["songStartSample"],
            (juce::int64) (double) msg["lengthSamples"]);
        return {};
    }

    if (cmd == "set_channel_send") {
        auto err = host.setChannelSend(
            msg["channelId"].toString(),
            msg["sendId"].toString(),
            msg["targetChannelId"].toString(),
            msg["targetInput"].toString());
        auto* o = new juce::DynamicObject();
        o->setProperty("event",  err.isEmpty() ? juce::var("channel_send_set") : juce::var("error"));
        o->setProperty("channelId", msg["channelId"]);
        o->setProperty("sendId",    msg["sendId"]);
        if (err.isNotEmpty()) o->setProperty("error", err);
        return juce::var(o);
    }

    if (cmd == "remove_channel_send") {
        host.removeChannelSend(msg["channelId"].toString(),
                               msg["sendId"].toString());
        return {};
    }

    auto* o = new juce::DynamicObject();
    o->setProperty("event", "unknown_cmd");
    o->setProperty("cmd", cmd);
    return juce::var(o);
}

} // namespace nasty
