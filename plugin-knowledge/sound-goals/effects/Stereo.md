---
category: Stereo
type: effect
---

# Stereo Tools

Width control — make it wider, narrow it, mid/side processing, panning tricks. Reach for these on "make it wider," "narrow the low end," "spread it out," "mid/side," "pan," "stereo image."

## Options

### AUVectorPanner

- **Character:** Clean, neutral, geometric — a positional panner, not a coloring effect. No tonal character of its own; it only relocates the source in the pan/surround field.
- **Best for:** Automated movement of a source around the listener in surround/immersive projects; static placement at specific azimuth/elevation angles; simple vector-based auto-pan when driven by automation.
- **Emotional tags:** spatial, immersive, cinematic, motion, disorienting (when swept quickly)
- **Comparison:** Much more basic and utilitarian than dedicated auto-panners like Cableguys PanShaper or Melda MStereoSpread; unlike HRTFPanner or AUSphericalHeadPanner it does not attempt binaural head modeling — it is a straight vector/angle panner. Best thought of as a developer-grade reference tool rather than a creative stereo widener.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="AUVectorPanner", position="post")` — then automate Azimuth (and Elevation for 3D busses) for movement. Requires a surround-capable output bus for full effect; on stereo it behaves as a plain L/R panner.

### AUSphericalHeadPanner

- **Character:** Clinical, technical binaural positioning — simulates how a sound would reach the two ears using a spherical head model. Not a coloring or widening effect; more of a 3D placement tool.
- **Best for:** Placing a mono source at a specific azimuth/elevation/distance around a listener for headphone (binaural) playback; experimental spatial sketches; developer/demo use.
- **Emotional tags:** spatial, immersive, heady, experimental, VR-ish
- **Comparison:** Much more basic and less musical than modern binaural panners (dearVR, Waves Nx, IEM plugins); comparable in concept to AUHRTFPanner but using a simpler spherical-head model rather than measured HRTFs. Not a stereo widener like Ozone Imager or bx_stereomaker.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="aupn sphr appl")` — Apple AU panner unit; host must support AU panner/spatialization units and route a mono source in. No named factory presets; automate azimuth/elevation/distance for movement.

### HRTFPanner

- **Character:** Binaural / 3D-headphone panning. Not a "wide" stereo effect — instead it places a mono source at a specific point in 3D space around the listener's head using HRTF convolution. Sounds spatially convincing on headphones, largely collapses on speakers.
- **Best for:** Binaural mixes, ASMR, VR/360 audio, immersive sound design, positioning individual mono elements (whispers, foley, ambience beds) around the listener. Useful when you want a source to feel behind, above, or beside the listener rather than just left/right.
- **Emotional tags:** immersive, spatial, cinematic, intimate, uncanny, 3D, headphone-first
- **Comparison:** Unlike a standard pan pot or a stereo widener (e.g. Ozone Imager, bx_stereomaker), HRTFPanner encodes elevation and front/back cues via ear-shaped filtering. It is closer in intent to dearVR MONO, Waves Nx, or IEM BinauralDecoder than to a mix-bus stereo tool. Simpler and lower-quality than dedicated commercial binaural panners, but free and built into macOS.
- **How to use:** `add_plugin_effect(channel_id=..., plugin_id="aupn/hrtf/appl", preset_name=None)` then automate `Azimuth`, `Elevation`, `Distance`, and `Gain`. Feed a mono source; monitor on headphones. Note: many DAWs will not expose this AU as an insert — prefer AUSpatialMixer or a third-party binaural panner if the host refuses to load it.

### Surge XT Effects — Stereo algorithms (Rotary, Ensemble, Chorus can widen)

- **Character:** thickens and widens the source signal via modulation-based stereo spread
- **Best for:** widening synths and pads, adding movement across the stereo field
- **Emotional tags:** wide, moving, dreamy
- **How to use:** `add_plugin_effect(channel_id="<target>", plugin_id="<Surge XT Effects id>")` then `set_plugin_param` with `param_name="FX Type"` to select a stereo-affecting algorithm. See `plugins/surge-xt-effects.md`.

## Common recipes

- **Widen a mono pad:** Surge Effects → Chorus or Ensemble, moderate depth.
- **Rotary width on organ:** Surge Effects → Rotary, alternate slow/fast speeds.

## Comparisons

No dedicated stereo tools available currently — we're leaning on modulation effects to create width.

## What we're missing

- No dedicated stereo widener (Voxengo MSED, iZotope Ozone Imager 2 free)
- No true mid/side processor
- No panning/auto-pan LFO effect

**Recommendation:** if the user needs precise stereo control (e.g., "narrow the bass, widen the highs"), we can't currently do it well — bundling a free stereo tool would fix this gap.
