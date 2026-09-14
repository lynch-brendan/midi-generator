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

  // Tier 1 auto-installer — silent download + install for OSS plugins.
  // installPluginAuto returns a promise that resolves to {ok, error?} once
  // the whole flow completes. Progress updates fire as `install-progress`
  // events with { pluginId, status, percent?, error? } — subscribe via
  // onInstallProgress. listAutoInstallable returns the set of plugin ids
  // routable through this path (rest fall back to openExternal).
  installPluginAuto: (pluginId) => ipcRenderer.invoke('install-plugin-auto', pluginId),
  listAutoInstallable: () => ipcRenderer.invoke('list-auto-installable-plugins'),
  onInstallProgress: (fn) => {
    const handler = (_evt, payload) => fn(payload);
    ipcRenderer.on('install-progress', handler);
    return () => ipcRenderer.removeListener('install-progress', handler);
  },

  // Tier 2 in-app browser installer — opens vendor page in a child
  // BrowserWindow, intercepts the file download when the user clicks
  // Download on that page, and runs the installer silently. Same
  // install-progress event stream as installPluginAuto (statuses:
  // opening-page, downloading, installing, done, error). `name` is
  // shown in the loading screen while the vendor page fetches.
  installPluginViaWeb: (pluginId, url, name, hint, opts) => ipcRenderer.invoke('install-plugin-via-web', { pluginId, url, name, hint, opts: opts || {} }),

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

    // Kill + respawn the audio engine subprocess so it re-scans the plugin
    // folders. Used by onboarding on "I'm done" — after fresh installs the
    // engine's cached plugin_list is stale until restart.
    restart: () => ipcRenderer.invoke('restart-audio-engine'),

    // Disk-truth listing of every plugin bundle installed on the user's Mac.
    // Onboarding uses this for the verification report so it works even
    // before the engine has re-scanned.
    listInstalledFiles: () => ipcRenderer.invoke('list-installed-plugin-files'),

    // Subscribe to engine events. Returns an unsubscribe function.
    onEvent: (fn) => {
      const handler = (_evt, msg) => fn(msg);
      ipcRenderer.on('engine-event', handler);
      return () => ipcRenderer.removeListener('engine-event', handler);
    },
  },
});
