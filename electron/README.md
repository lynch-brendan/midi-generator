# Nasty — Desktop

Electron shell around the Nasty DAW.

## Run in development

```sh
cd electron
npm install
npm start
```

This opens `web/nasty.html` as a native desktop window.

## Build a distributable

```sh
npm run dist:mac    # → dist/Nasty-0.1.0-arm64.dmg (etc)
npm run dist:win    # → dist/Nasty Setup 0.1.0.exe
```

Signing and notarization aren't wired up yet — the first `.dmg` will
warn users on install. That's fine for internal testing; we'll add
codesigning before publishing.

## What's here (and what isn't)

- **Is:** native window, native menu bar, F5-F10 window toggles,
  ⌘S/⌘O/⌘E/⌘N, Cmd+Q, offline load of the DAW UI.
- **Isn't yet:** VST/AU plugin hosting. That needs a native audio
  engine (JUCE/CLAP host) wired to the UI via IPC — separate work.

## How it loads the UI

`main.js` looks for `../web/nasty.html` (dev) then falls back to
`process.resourcesPath/web/nasty.html` (packaged build). The `preload.js`
sets `window.nasty.apiBase` so chat calls hit `museaimusician.com`
instead of a relative URL that doesn't exist under `file://`.
