const { app, BrowserWindow, Menu, shell } = require('electron');
const path = require('path');
const fs = require('fs');

let mainWindow;

function findNastyHtml() {
  // Dev: web/nasty.html is one level up from electron/
  const devPath = path.join(__dirname, '..', 'web', 'nasty.html');
  if (fs.existsSync(devPath)) return devPath;
  // Packaged: extraResources copies web/ into resources
  const prodPath = path.join(process.resourcesPath, 'web', 'nasty.html');
  if (fs.existsSync(prodPath)) return prodPath;
  return devPath;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 560,
    backgroundColor: '#252932',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    trafficLightPosition: { x: 12, y: 6 },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
  });

  mainWindow.loadFile(findNastyHtml());
  mainWindow.once('ready-to-show', () => mainWindow.show());

  // External links open in the OS browser, not inside Nasty
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

function sendCmd(cmd) {
  if (!mainWindow) return;
  mainWindow.webContents.executeJavaScript(
    `typeof runCmd === 'function' && runCmd(${JSON.stringify(cmd)})`
  ).catch(() => {});
}

function clickBtn(id) {
  if (!mainWindow) return;
  mainWindow.webContents.executeJavaScript(
    `document.getElementById(${JSON.stringify(id)})?.click()`
  ).catch(() => {});
}

function buildMenu() {
  const isMac = process.platform === 'darwin';
  const template = [
    ...(isMac ? [{
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    }] : []),
    {
      label: 'File',
      submenu: [
        { label: 'New Song',       accelerator: 'CmdOrCtrl+N', click: () => clickBtn('clear-btn') },
        { type: 'separator' },
        { label: 'Save…',          accelerator: 'CmdOrCtrl+S', click: () => clickBtn('save-btn') },
        { label: 'Open…',          accelerator: 'CmdOrCtrl+O', click: () => clickBtn('load-btn') },
        { type: 'separator' },
        { label: 'Export WAV',     accelerator: 'CmdOrCtrl+E', click: () => clickBtn('export-btn') },
        { type: 'separator' },
        isMac ? { role: 'close' } : { role: 'quit' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: 'Add',
      submenu: [
        { label: 'Channel…',   click: () => sendCmd('add-channel') },
        { label: 'Pattern…',   click: () => sendCmd('add-pattern') },
        { label: 'Mixer Insert', click: () => sendCmd('add-insert') },
      ],
    },
    {
      label: 'View',
      submenu: [
        { label: 'Playlist',      accelerator: 'F5',  click: () => sendCmd('toggle-playlist') },
        { label: 'Channel Rack',  accelerator: 'F6',  click: () => sendCmd('toggle-rack') },
        { label: 'Piano Roll',    accelerator: 'F7',  click: () => sendCmd('toggle-pr') },
        { label: 'Browser',       accelerator: 'F8',  click: () => sendCmd('toggle-browser') },
        { label: 'Mixer',         accelerator: 'F9',  click: () => sendCmd('toggle-mixer') },
        { label: 'AI Chat',       accelerator: 'F10', click: () => sendCmd('toggle-chat') },
        { type: 'separator' },
        { role: 'reload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Tools',
      submenu: [
        { label: 'Record microphone',   click: () => sendCmd('mic-rec') },
        { label: 'Record MIDI keyboard', click: () => sendCmd('midi-rec') },
      ],
    },
    { role: 'windowMenu' },
    {
      role: 'help',
      submenu: [
        { label: 'Keyboard shortcuts…', click: () => sendCmd('help-shortcuts') },
        { type: 'separator' },
        { label: 'Nasty — an AI-native DAW', enabled: false },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

app.whenReady().then(() => {
  createWindow();
  buildMenu();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
