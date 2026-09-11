---
name: Surge XT
verified: false
last_updated: 2026-09-11
preset_paths:
  - "~/Documents/Surge XT/Patches:.fxp"
  - "/Library/Application Support/Surge XT/Patches:.fxp"
  - "C:\\ProgramData\\Surge XT\\Patches:.fxp"
  - "%USERPROFILE%\\Documents\\Surge XT\\Patches:.fxp"
---

# Surge XT

Free and open-source hybrid synthesizer instrument (VST3/AU/CLAP) maintained by the Surge Synth Team.

## Presets on disk

Surge XT uses `.fxp` patch files organized into categorized subfolders. All patches and wavetables need to be categorized — a patch belongs at `Surge XT/Patches/<Category>/<PatchName>.fxp`.

Locations (from the official manual):
- **Windows factory:** `C:\ProgramData\Surge XT`
- **Windows user:** `C:\Users\<username>\Documents\Surge XT`
- **macOS factory:** `/Library/Application Support/Surge XT`
- **macOS user:** `~/Documents/Surge XT`
- **Linux factory:** `/usr/share/surge-xt` with a standard install
- **Linux user:** `~/Documents/Surge XT`

Surge XT creates the user directory when you store a patch or change the user default settings for the first time. At startup, Surge XT scans for all information (skins, patches, wavetables, etc.) from both the Factory folder and the User folder on your system. The exact resolved paths for the current install are always visible in Menu → About Surge XT.

Patches live under a `Patches/` subfolder; wavetables under `Wavetables/`; FX presets under `FX Presets/`, etc. Surge XT forces content type into subfolders (FX Presets, Patches, Wavetables, etc.).

## Notable parameters

Surge XT is a dual-scene subtractive/wavetable/FM synth. Top-level parameters worth automating:

- **Category / Patch** — browser-driven selection (not a normal automatable parameter; changing the patch replaces most state)
- **Scene A / Scene B** volume, pan, and Scene mode (Single / Split / Channel Split / Dual)
- **Filter Cutoff / Resonance** (per filter, per scene)
- **Amp EG / Filter EG** (A/D/S/R) per scene
- **Character** (Warm / Neutral / Bright) — global tone shaping
- **Global Volume**

Character and global volume (for XT 1.0 and above patches) are stored per patch.

## Quirks

- **Real preset browser is inside the GUI.** The categorized patch tree with author/category metadata is only fully navigable through Surge XT's own browser; the host's generic program list is not the authoritative view.
- **Factory vs User split.** The Factory folder is installed in an administrator-writable central location, and the User folder is in your user documents area. Third-party/user patches should always go under the User folder — if you reinstall Surge XT, you will lose any changes you made to the content of the factory folder, including custom patches and skins; the Surge XT installer never changes files in the user area.
- **Categorization is mandatory.** A `.fxp` dropped directly into `Patches/` (with no category subfolder) may not appear as expected — patches must live inside a category subfolder.
- **Data paths are user-configurable.** The About screen shows the currently resolved paths; users can override defaults, so scanning only the default paths may miss patches on some installs.
- **Installer alt-drive bug (historical).** Users have reported that after installing to an alternate drive, the only patch available is "Init" and the "Factory Data" path listed in About Surge does not exist — worth checking About before assuming the default path is populated.
- **Instrument, not effect.** Surge XT is primarily an instrument plugin, not a standalone program (there is also an FX build "Surge XT Effects" that is a separate plugin).
- **Patch categories to expect:** Basses, Leads, Pads, Keys, Plucks, Percussion, Templates, etc. (folder names are literal and case-sensitive on Linux/macOS).

## Common recipes (optional)

Rather than tweaking from Init, it's usually faster to load a factory patch from the appropriate category folder and modify:

- **Bass:** load from `Patches/Basses/`, then lower Filter Cutoff and shorten Amp EG Release.
- **Lead:** load from `Patches/Leads/`, enable mono/legato in Scene mode, add portamento.
- **Pad:** load from `Patches/Pads/`, lengthen Amp EG Attack/Release, engage Scene B for detuned layering.
