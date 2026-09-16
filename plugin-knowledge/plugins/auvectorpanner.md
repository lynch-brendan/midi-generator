---
name: AUVectorPanner
verified: false
last_updated: 2026-09-16
---

# AUVectorPanner

Apple's built-in Audio Unit panner that positions a mono/stereo source within a 2D/3D vector space for surround and immersive placement.

## Presets on disk
Not applicable — this plugin exposes presets via the standard AU program API.

## Notable parameters
- **Azimuth** — horizontal angle of the source around the listener
- **Elevation** — vertical angle of the source relative to the listener
- **Distance / Gain** — perceived distance from the listener
- (Exact parameter set follows Apple's standard Panner Audio Unit parameter conventions)

## Quirks
- <cite index="2-1,2-2">Ships as one of Apple's demonstration panner Audio Units introduced in Mac OS X Leopard, alongside AUSoundFieldPanner, AUSphericalHeadPanner, and HRTFPanner</cite>; it is essentially a developer/reference plug-in rather than a polished creative tool.
- Categorized by Core Audio as a `kAudioUnitType_Panner`, so many DAWs (notably Logic Pro) do not expose it in the normal effect slot list — <cite index="1-1,1-2">it historically has not appeared as a usable insert in Logic</cite> and is typically only available in hosts like AU Lab or custom Core Audio apps.
- Requires the host to be configured with a multichannel/surround output bus for the panning to be meaningful; on a stereo bus it collapses to simple L/R placement.
- No GUI beyond the generic AU parameter view in most hosts.
- <cite index="5-2,5-3">Positions audio within a 2D or 3D vector space, useful for automating the movement of a sound source around the listener for dynamic audio scenes</cite>.
