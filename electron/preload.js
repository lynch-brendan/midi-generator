const { contextBridge, ipcRenderer } = require('electron');

// Bridge minimal safe API into the renderer.
// nasty.html detects window.nasty?.isDesktop and points fetch() at apiBase.
contextBridge.exposeInMainWorld('nasty', {
  isDesktop: true,
  platform: process.platform,
  apiBase: 'https://museaimusician.com',

  // TEMP: dump preset states to /tmp so Claude can bake them as defaults.
  dumpPresetStates: (json) => ipcRenderer.invoke('dump-preset-states', json),

  // Open an external URL in the user's default browser. Used by the
  // onboarding bundle downloader to send users to vendor installer pages
  // for plugins we can't auto-install (Valhalla, TDR, Klanghelm, u-he, ...).
  openExternal: (url) => ipcRenderer.invoke('open-external', url),

  // Path to the bundled General MIDI SoundFont on disk.
  sf2Path: () => ipcRenderer.invoke('nasty-sf2-path'),

  // File-system reach for plugin-knowledge preset loading. Renderer asks
  // main for a directory of preset files (recursive) or the raw bytes of
  // a specific file. Both go through IPC — renderer has no direct fs.
  fs: {
    listPresets: (dir, ext) => ipcRenderer.invoke('nasty-list-presets', { dir, ext }),
    readAsBase64: (filePath) => ipcRenderer.invoke('nasty-read-base64', filePath),
  },

  // Audio engine bridge (VST/AU plugin hosting).
  engine: {
    // Send a command to the audio engine (JSON serialisable).
    send: (msg) => ipcRenderer.invoke('engine-cmd', msg),

    // Check whether the engine is running and finished its initial plugin scan.
    status: () => ipcRenderer.invoke('engine-status'),

    // Subscribe to engine events. Returns an unsubscribe function.
    onEvent: (fn) => {
      const handler = (_evt, msg) => fn(msg);
      ipcRenderer.on('engine-event', handler);
      return () => ipcRenderer.removeListener('engine-event', handler);
    },
  },
});
