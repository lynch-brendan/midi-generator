const { app, BrowserWindow, Menu, shell, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const readline = require('readline');

// Prevent multiple Nasty windows from stacking up when `npm start` is re-run
// while another instance is still around. Second launch just focuses the
// existing window instead of spawning a fresh (and often blank) one.
const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
  process.exit(0);
}

let mainWindow;
let audioEngineProc = null;
let engineReady = false;
let engineStdinRl = null;

function findAudioEngineBinary() {
  const candidates = [
    path.join(__dirname, '..', 'audio-engine', 'build', 'nasty-audio-engine_artefacts', 'nasty-audio-engine'),
    path.join(__dirname, '..', 'audio-engine', 'build', 'nasty-audio-engine_artefacts', 'Release', 'nasty-audio-engine'),
    path.join(__dirname, '..', 'audio-engine', 'build', 'nasty-audio-engine'),
    path.join(process.resourcesPath || '', 'audio-engine', 'nasty-audio-engine'),
  ];
  return candidates.find(p => p && fs.existsSync(p));
}

// Spawn the native audio engine and pipe JSON lines both ways.
function startAudioEngine() {
  const bin = findAudioEngineBinary();
  if (!bin) {
    console.log('[nasty] audio engine binary not found — VST hosting disabled. Build it with: cd audio-engine/build && cmake --build .');
    return;
  }
  console.log('[nasty] spawning audio engine:', bin);
  audioEngineProc = spawn(bin, [], { stdio: ['pipe', 'pipe', 'pipe'] });

  const rl = readline.createInterface({ input: audioEngineProc.stdout });
  rl.on('line', (line) => {
    let msg;
    try { msg = JSON.parse(line); }
    catch { return; }
    if (msg.event === 'ready') engineReady = true;
    // Forward every engine event to the renderer as 'engine-event'.
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('engine-event', msg);
    }
  });

  // Engine stderr is noisy (plugins print init logs). Keep visible in dev console only.
  audioEngineProc.stderr.on('data', (buf) => {
    process.stderr.write('[engine] ' + buf.toString());
  });

  audioEngineProc.on('exit', (code) => {
    console.log('[nasty] audio engine exited', code);
    audioEngineProc = null;
    engineReady = false;
  });
}

function stopAudioEngine() {
  if (audioEngineProc) {
    try { audioEngineProc.kill('SIGTERM'); } catch {}
    audioEngineProc = null;
    engineReady = false;
  }
}

// Renderer → engine: forward JSON commands over stdin.
ipcMain.handle('engine-cmd', (_evt, msg) => {
  if (!audioEngineProc || !audioEngineProc.stdin.writable) {
    return { ok: false, error: 'audio engine not running' };
  }
  try {
    audioEngineProc.stdin.write(JSON.stringify(msg) + '\n');
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
});

ipcMain.handle('engine-status', () => ({
  running: !!audioEngineProc,
  ready: engineReady,
}));

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
    icon: path.join(__dirname, 'build', process.platform === 'win32' ? 'icon.ico' : 'icon.png'),
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
  startAudioEngine();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// If a second `npm start` fires while Nasty is already running, focus the
// existing window instead of opening a duplicate.
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', stopAudioEngine);
