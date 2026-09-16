---
name: AUNetSend
verified: false
last_updated: 2026-09-16
---

# AUNetSend

Apple's built-in AudioUnit for streaming audio over a local network to a paired AUNetReceive instance on another Mac.

## Presets on disk
Not applicable — this plugin exposes presets via the standard VST/AU program API.

## Notable parameters
- **Bonjour Name:** The service name this sender advertises on the local network for AUNetReceive to discover.
- **Password:** Optional password required by receivers to connect to this stream.
- **Format / Bit Depth:** Streaming format selection (e.g., PCM 16-bit, PCM 24-bit, PCM 32-bit float, Apple Lossless, AAC) — trades bandwidth vs. quality/latency.
- **Connection status:** Read-only indicator showing whether a receiver is currently connected.

## Quirks
- This is a **utility/routing plugin**, not a sound-shaping effect. It passes audio through unchanged while sending a copy over the network.
- Requires **AUNetReceive** on another Mac on the same local network (Bonjour/mDNS must be reachable).
- Introduces network latency; not suitable for tight monitoring or realtime performance sync.
- macOS-only (AudioUnit format, Apple system component).
- Not musically useful on its own — an AI music assistant should not insert this as a creative effect.
- If the receiver is not connected, audio still passes through locally but nothing is transmitted.
