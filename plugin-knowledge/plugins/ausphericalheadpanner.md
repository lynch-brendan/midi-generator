---
name: AUSphericalHeadPanner
verified: false
last_updated: 2026-09-16
---

# AUSphericalHeadPanner

Apple-supplied AudioUnit panner that simulates binaural localization using a spherical model of the human head; shipped by Apple as a developer demo of the AU panner unit API.

## Presets on disk
Not applicable — this plugin exposes presets via the standard VST/AU program API. No known factory preset library on disk.

## Notable parameters
- Azimuth (horizontal angle of the virtual source around the listener)
- Elevation (vertical angle of the virtual source)
- Distance / Radius (perceived source distance from the listener)
- (Panner units are driven via the AU spatialization/panner API rather than a large parameter list; exact exposed parameters depend on the host.)

## Quirks
- Ships as one of Apple's four bundled panner AUs (AUSoundFieldPanner, AUSphericalHeadPanner, AUVectorPanner, AUHRTFPanner); it is essentially a developer example / starting point for panner units, not a polished production plugin.
- Requires a host that supports AU panner units and provides a spatialization UI (e.g. AU Lab). In many hosts (older Logic, Audacity) the plugin appears in the list but produces no useful UI/effect — Audacity users have reported that applying it does nothing visible and can leave the project sounding muffled.
- Not a stereo-in / stereo-out insert in the conventional sense: it takes a mono source and renders it into a multichannel/binaural field, so behavior depends heavily on host bus configuration.
- No documented factory presets; parameter naming and ranges are minimally documented by Apple.
