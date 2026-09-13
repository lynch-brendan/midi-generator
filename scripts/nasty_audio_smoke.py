#!/usr/bin/env python3
# Headless smoke test for the Nasty audio engine.
#
# What it does:
#   1. Spawns the audio engine binary as a subprocess.
#   2. Waits for the `audio_ready` event.
#   3. Sends `list_plugins`, finds Dexed.
#   4. Sends `load_plugin` with Dexed on a test channel.
#   5. Sends a `note_on` (proves MIDI routes without hanging).
#   6. Sends `transport_get` and verifies a response comes back
#      (round-trip proves the earlier commands drained without deadlock).
#   7. Cleanly shuts the engine down.
#
# Exits 0 on success, non-zero on any failure with a clear stderr message.
#
# What this catches:
#   - Engine fails to boot
#   - Plugin scan hangs or fails
#   - load_plugin deadlocks (the class of bug fixed in 5935d48)
#   - MIDI/graph race conditions that would hang subsequent commands
#   - Engine crash on any of the above
#
# What this does NOT catch (yet):
#   - Silent audio failure (plugin loads but produces no output).
#     Detecting this needs either an engine-side RMS query or system
#     audio capture — future improvement. For now, if the smoke test
#     passes, run Nasty manually and confirm you hear a note.

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENGINE_BIN = os.path.join(
    REPO_ROOT,
    "audio-engine",
    "build",
    "nasty-audio-engine_artefacts",
    "nasty-audio-engine",
)

# The plugin we probe — Dexed is free, small, deterministic, and always
# available on Brendan's setup. If Dexed isn't installed, the test skips
# the load step and just verifies the engine boots + responds.
TARGET_PLUGIN = "Dexed"
TEST_CHANNEL = "smoke_test_ch"

# Total budget. Fresh plugin scan can take ~30s the first time; cached
# boot is a few seconds. 60s covers both comfortably.
TIMEOUT_SEC = 60


def fail(msg, engine_stderr=None):
    print(f"[SMOKE FAIL] {msg}", file=sys.stderr)
    if engine_stderr:
        print("--- last engine stderr ---", file=sys.stderr)
        print(engine_stderr, file=sys.stderr)
    sys.exit(1)


def main():
    if not os.path.isfile(ENGINE_BIN):
        fail(f"engine binary not found at {ENGINE_BIN} — build it first "
             "(cd audio-engine/build && cmake --build .)")

    # Line-buffered stdio in both directions.
    env = os.environ.copy()
    proc = subprocess.Popen(
        [ENGINE_BIN],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        bufsize=1,
        text=True,
    )

    # Queues for events. Stdout carries JSON events; stderr carries free
    # log lines (we capture the tail for error reporting).
    events = queue.Queue()
    stderr_lines = []

    def read_stdout():
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.put(json.loads(line))
                except json.JSONDecodeError:
                    # Non-JSON stdout — shouldn't happen but don't crash on it.
                    pass
        except Exception:
            pass

    def read_stderr():
        try:
            for line in proc.stderr:
                stderr_lines.append(line.rstrip())
                # Keep last 40 lines only.
                if len(stderr_lines) > 40:
                    stderr_lines.pop(0)
        except Exception:
            pass

    threading.Thread(target=read_stdout, daemon=True).start()
    threading.Thread(target=read_stderr, daemon=True).start()

    def send(msg):
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def wait_for_event(name, timeout):
        # Consume events off the queue until we see the target event or run
        # out of time. Ignores unrelated events (transport_position spam,
        # scanning progress).
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                ev = events.get(timeout=0.5)
            except queue.Empty:
                if proc.poll() is not None:
                    fail(f"engine exited (code {proc.returncode}) while "
                         f"waiting for '{name}'",
                         engine_stderr="\n".join(stderr_lines))
                continue
            if ev.get("event") == name:
                return ev
            if ev.get("event") == "error":
                fail(f"engine returned error while waiting for '{name}': "
                     f"{ev}", engine_stderr="\n".join(stderr_lines))
        fail(f"timed out after {timeout}s waiting for '{name}'",
             engine_stderr="\n".join(stderr_lines))

    try:
        # --- 1. Wait for boot ---
        print("[smoke] waiting for engine boot...")
        wait_for_event("audio_ready", TIMEOUT_SEC)
        print("[smoke] engine booted, audio device live")

        # --- 2. List plugins, find Dexed ---
        send({"cmd": "list_plugins"})
        listing = wait_for_event("plugin_list", 10)
        plugins = listing.get("plugins") or []
        dexed = next(
            (p for p in plugins if isinstance(p, dict)
             and p.get("name") == TARGET_PLUGIN),
            None,
        )

        if not dexed:
            # Dexed isn't installed — don't fail. Engine booted and
            # responded, that's still a valid smoke test. Just report.
            print(f"[smoke] {TARGET_PLUGIN} not installed — skipping "
                  "load_plugin/note_on/transport_get sequence")
            print("[smoke] engine boot + list_plugins round-trip OK")
            print("[SMOKE OK]")
            return

        print(f"[smoke] found {TARGET_PLUGIN} (id={dexed.get('id')})")

        # --- 3. Load Dexed on a test channel ---
        send({
            "cmd": "load_plugin",
            "channelId": TEST_CHANNEL,
            "pluginId": dexed["id"],
            "state": "",
            "presetName": "",
        })
        wait_for_event("plugin_loaded", 15)
        print(f"[smoke] {TARGET_PLUGIN} loaded on {TEST_CHANNEL}")

        # --- 4. Send a note_on. No direct response, but shouldn't hang.
        send({
            "cmd": "note_on",
            "channelId": TEST_CHANNEL,
            "pitch": 60,
            "velocity": 0.8,
        })

        # --- 5. transport_get round-trip proves the noteOn drained the
        #        stdin queue without deadlocking.
        send({"cmd": "transport_get"})
        wait_for_event("transport_state", 5)
        print("[smoke] transport_get round-trip OK — noteOn didn't hang")

        # --- 6. Clean up: note off + unload.
        send({
            "cmd": "note_off",
            "channelId": TEST_CHANNEL,
            "pitch": 60,
        })
        send({"cmd": "unload_plugin", "channelId": TEST_CHANNEL})
        # Small settle time before shutdown.
        time.sleep(0.2)

        print("[SMOKE OK]")
    finally:
        # Cleanly shut the engine down. It runs a message loop with no
        # explicit "quit" command, so SIGTERM is the right way to stop it.
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
