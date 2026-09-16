---
name: AUNetReceive
verified: false
last_updated: 2026-09-16
---

# AUNetReceive

Apple system Audio Unit generator that receives a network audio stream from a paired AUNetSend instance over LAN/Bonjour.

## Presets on disk
Not applicable — no factory preset library. Configuration (port, password, discovered sender) is stored per-host session.

## Notable parameters
- **Bonjour Name / Sender list:** Browse and select an AUNetSend provider advertised on the network (Bonjour service type `_apple-ausend._tcp.`).
- **Hostname / IP address:** Manual connection field, used when Bonjour discovery fails (recommended on macOS 10.13+ due to an IPv6 discovery issue).
- **Port:** Default TCP/UDP port 52800; must be reachable/open on the router if crossing networks.
- **Password:** Optional shared secret to secure the stream between sender and receiver.
- **Data Format:** Set on the AUNetSend side (uncompressed PCM, Apple Lossless, compressed AIFF, or AAC) — AUNetReceive negotiates whatever the sender provides.

## Quirks
- It is a **Generator** Audio Unit (type `augn`, subtype `nrcv`, manufacturer `appl`), not an instrument or effect. Many AU hosts do not expose Generator AUs at all — historically absent from Digital Performer, GarageBand plugin menus, MainStage, etc. Logic Pro and AU Lab / Hosting AU are known-good hosts; Rogue Amoeba's Audio Hijack added explicit Generator support.
- Produces silence until a valid AUNetSend peer is connected. There is no built-in test tone.
- On macOS 10.13+ Bonjour auto-discovery may fail to see senders (IPv6 issue); entering the sender's IP manually is the workaround.
- Requires port 52800 (TCP and UDP) to be open when routing across a router/firewall.
- Purely a transport/routing utility — it has no DSP, no sound-shaping controls, and no musical character of its own.
- Not intended for creative sound design; use is limited to distributing audio between machines/hosts on a LAN.
