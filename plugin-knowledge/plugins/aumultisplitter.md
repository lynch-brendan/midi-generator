---
name: AUMultiSplitter
verified: false
last_updated: 2026-09-16
---

# AUMultiSplitter

Apple system Audio Unit (subtype `mspl`, type `aumx`) used internally by AVAudioEngine to route one signal to multiple destinations — not a musical effect.

## Presets on disk
Not applicable — no factory preset library. This is a system-level routing/mixer utility instantiated automatically by AVAudioEngine.

## Notable parameters
None documented for musical use. AUMultiSplitter is an internal utility exposed by Apple's AudioUnit framework; it is created by the engine when one-to-many connections are made rather than being loaded by users as a creative plugin.

## Quirks
- Not a user-facing plugin. It appears in exhaustive `auval`/component listings as `aumx mspl appl` (Apple: AUMultiSplitter) alongside AUMixer, AUMatrixMixer, AUSplitter, etc., but is intended for internal graph routing.
- Instantiated automatically: as documented by developers working with AVAudioEngine, the engine creates an AUMultiSplitter instance whenever a node has one-to-many output connections. It is not something a producer would insert on a channel for musical purposes.
- No GUI, no musical parameters, no presets — should not be surfaced as a creative effect in a music-production context.
