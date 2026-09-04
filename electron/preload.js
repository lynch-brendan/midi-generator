const { contextBridge, ipcRenderer } = require('electron');

// Bridge minimal safe API into the renderer.
// nasty.html detects window.nasty?.isDesktop and points fetch() at apiBase.
contextBridge.exposeInMainWorld('nasty', {
  isDesktop: true,
  platform: process.platform,
  apiBase: 'https://museaimusician.com',

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
