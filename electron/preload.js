const { contextBridge } = require('electron');

// Bridge minimal safe API into the renderer.
// nasty.html detects window.nasty?.isDesktop and points fetch() at apiBase.
contextBridge.exposeInMainWorld('nasty', {
  isDesktop: true,
  platform: process.platform,
  apiBase: 'https://museaimusician.com',
});
