---
name: AURoundTripAAC
verified: false
last_updated: 2026-09-16
---

# AURoundTripAAC

Apple's Mastered-for-iTunes QA utility Audio Unit that A/Bs AAC-encoded audio against the original source to check for clipping and encoding artifacts.

## Presets on disk
Not applicable — no factory preset library. This is a metering/listening-test utility, not a sound-design tool.

## Notable parameters
- **Audition tab (Source / Encoded):** switches monitoring between the original source audio and the AAC-encoded version.
- **Encoded Format pop-up:** selects the AAC encoding format to compare against; a Custom option is available for formats not in the list.
- **Clip / Peak indicators + Reset:** turn red when clipping is detected; Reset clears the indicators.
- **Show Details:** reveals per-channel highest peak, sample peak, inter-sample peak, and clipping counts for both source and encoded audio.
- **Listening Test (Source / A / B):** launches a double-blind ABX test where source is randomly assigned to A or B each cycle.
- **Training Mode:** shows the answer after each pick; intended for practice only, not for scoring a real ABX run.

## Quirks
- Not a musical effect — it's a mastering/QA tool for verifying AAC (iTunes Plus / Apple Digital Masters) encodes. Do not insert it on musical tracks expecting audible processing.
- Requires a host that can feed it audio (Logic Pro, GarageBand, AU Lab, or any AU host); AU Lab was Apple's reference host for this workflow.
- For a valid ABX result, run a predetermined number of test cycles before revealing results; Training Mode invalidates statistical significance.
- macOS-only (AudioUnit format). No Windows / VST3 equivalent from Apple.
- Does not itself encode files to AAC as an output — it's for auditioning and clip/peak analysis of the roundtrip only.
