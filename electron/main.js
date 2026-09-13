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
let audioReady = false;
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

// On first launch, copy any bundled SFZ folders into the user's Sfizz
// default folder so they show up in Sfizz's file picker without setup.
// Idempotent: only copies folders that don't already exist.
function seedBundledInstruments() {
  try {
    const devBundle  = path.join(__dirname, '..', 'audio-engine', 'bundled-instruments', 'sfz');
    const prodBundle = path.join(process.resourcesPath || '', 'bundled-instruments', 'sfz');
    const source = fs.existsSync(devBundle) ? devBundle
                 : fs.existsSync(prodBundle) ? prodBundle
                 : null;
    if (!source) return;
    const dest = path.join(require('os').homedir(), 'Documents', 'SFZ instruments');
    fs.mkdirSync(dest, { recursive: true });
    const entries = fs.readdirSync(source, { withFileTypes: true });
    for (const e of entries) {
      if (!e.isDirectory()) continue;
      const from = path.join(source, e.name);
      const to = path.join(dest, e.name);
      if (fs.existsSync(to)) continue;
      // Recursive copy (Node 16.7+ supports fs.cpSync).
      fs.cpSync(from, to, { recursive: true });
      console.log('[nasty] seeded instrument:', e.name);
    }
  } catch (e) {
    console.error('[nasty] seedBundledInstruments failed:', e);
  }
}

// Spawn the native audio engine and pipe JSON lines both ways.
function startAudioEngine() {
  const bin = findAudioEngineBinary();
  if (!bin) {
    console.log('[nasty] audio engine binary not found — VST hosting disabled. Build it with: cd audio-engine/build && cmake --build .');
    return;
  }
  // Point the engine at our bundled instruments folder so Sfizz + our
  // curated CC0/CC-BY sample libraries get scanned alongside the user's
  // system plugins. Dev: audio-engine/bundled-instruments. Prod: inside
  // Nasty.app/Contents/Resources.
  const devInstruments  = path.join(__dirname, '..', 'audio-engine', 'bundled-instruments');
  const prodInstruments = path.join(process.resourcesPath || '', 'bundled-instruments');
  const instrumentsPath = fs.existsSync(devInstruments) ? devInstruments
                        : fs.existsSync(prodInstruments) ? prodInstruments
                        : null;
  const engineEnv = { ...process.env };
  if (instrumentsPath) engineEnv.NASTY_INSTRUMENTS_PATH = instrumentsPath;
  // Path to the bundled General MIDI SoundFont — renderer sends this to the
  // engine when creating GM channels.
  const sf2Path = instrumentsPath ? path.join(instrumentsPath, 'GeneralUser.sf2') : '';
  engineEnv.NASTY_SF2_PATH = sf2Path;

  console.log('[nasty] spawning audio engine:', bin);
  if (instrumentsPath) console.log('[nasty] bundled instruments at:', instrumentsPath);
  audioEngineProc = spawn(bin, [], { stdio: ['pipe', 'pipe', 'pipe'], env: engineEnv });

  const rl = readline.createInterface({ input: audioEngineProc.stdout });
  rl.on('line', (line) => {
    let msg;
    try { msg = JSON.parse(line); }
    catch { return; }
    if (msg.event === 'ready') engineReady = true;
    if (msg.event === 'audio_ready') audioReady = !!(msg.deviceName && msg.outputChannels);
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
    audioReady = false;
  });
}

function stopAudioEngine() {
  if (audioEngineProc) {
    try { audioEngineProc.kill('SIGTERM'); } catch {}
    audioEngineProc = null;
    engineReady = false;
    audioReady = false;
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

ipcMain.handle('dump-preset-states', (_evt, json) => {
  try { fs.writeFileSync('/tmp/nasty-preset-states.json', json); return { ok: true }; }
  catch (e) { return { ok: false, error: String(e) }; }
});

ipcMain.handle('engine-status', () => ({
  running: !!audioEngineProc,
  ready: engineReady,
  audioReady,
}));

// Plugin-knowledge preset loading. Renderer asks main to list all files
// of a given extension under a directory (recursive, ~-expanded), or to
// read the raw bytes of a single file as base64. Used so cheatsheets can
// point at real preset folders on disk (Surge XT .fxp, Serum .fxp, etc.)
// and Claude can pick one by name.
ipcMain.handle('nasty-list-presets', async (_evt, { dir, ext }) => {
  const os = require('os');
  const expandHome = (p) => p.startsWith('~')
    ? path.join(os.homedir(), p.slice(1))
    : p;
  const target = expandHome(dir);
  const wantExt = '.' + String(ext || 'fxp').toLowerCase();
  const results = [];
  const walk = async (d) => {
    let entries;
    try { entries = await fs.promises.readdir(d, { withFileTypes: true }); }
    catch { return; }
    for (const e of entries) {
      const full = path.join(d, e.name);
      if (e.isDirectory()) { await walk(full); }
      else if (e.name.toLowerCase().endsWith(wantExt)) { results.push(full); }
    }
  };
  await walk(target);
  return results;
});

ipcMain.handle('nasty-read-base64', async (_evt, filePath) => {
  const os = require('os');
  const expandHome = (p) => p.startsWith('~')
    ? path.join(os.homedir(), p.slice(1))
    : p;
  try {
    const buf = await fs.promises.readFile(expandHome(filePath));
    return buf.toString('base64');
  } catch (e) {
    return '';
  }
});

// Onboarding downloader — opens vendor installer pages in the user's default
// browser. Sandbox: only allow http(s) URLs, no `file://` or JS URIs.
ipcMain.handle('open-external', async (_evt, url) => {
  try {
    if (typeof url !== 'string') return { ok: false, error: 'invalid url' };
    if (!/^https?:\/\//i.test(url)) return { ok: false, error: 'only http(s) urls allowed' };
    await shell.openExternal(url);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
});


// ---------------------------------------------------------------------------
// Tier 1 auto-install — silent download + install for OSS plugins with
// direct .pkg / .dmg URLs. Uses only Node built-ins + macOS `installer` and
// `hdiutil`. Renderer calls `install-plugin-auto` per plugin; we stream
// progress events back so the UI can show a real bar per install.
// ---------------------------------------------------------------------------

// Resolver map: plugin id → how to obtain the installer.
// - kind: 'direct'  → pkgUrl is a stable URL to a .pkg or .dmg file
// - kind: 'github'  → look up latest release from the repo, pick the asset
//                     matching assetMatch (macOS .pkg preferred, .dmg fallback)
const OSS_INSTALLERS = {
  'surge-xt': {
    kind: 'direct',
    // Surge XT ships an installer .pkg (not just a drag-install .dmg). URL
    // hardcoded from the manifest; when this goes stale (new release), just
    // bump it in one place. Long-term: switch to their releases feed.
    url: 'https://github.com/surge-synthesizer/releases-xt/releases/download/1.3.4/surge-xt-macOS-1.3.4.pkg',
    kindHint: 'pkg',
  },
  'dexed': {
    kind: 'github',
    owner: 'asb2m10',
    repo: 'dexed',
    assetMatch: /(mac|osx).*\.pkg$/i,
    assetFallback: /(mac|osx).*\.dmg$/i,
  },
  'sfizz': {
    kind: 'github',
    owner: 'sfztools',
    repo: 'sfizz',
    assetMatch: /macos.*\.pkg$/i,
    assetFallback: /macos.*\.dmg$/i,
  },
};

function isAutoInstallable(pluginId) {
  return Object.prototype.hasOwnProperty.call(OSS_INSTALLERS, pluginId);
}

// Resolve a plugin id to a concrete { url, kindHint } — kindHint is 'pkg' or
// 'dmg' derived from the URL. GitHub-hosted plugins hit api.github.com to
// find the latest release's macOS asset. Throws on any failure so the caller
// can report a clean error via IPC.
async function resolveInstallerUrl(pluginId) {
  const spec = OSS_INSTALLERS[pluginId];
  if (!spec) throw new Error(`no OSS installer registered for '${pluginId}'`);
  if (spec.kind === 'direct') {
    return { url: spec.url, kindHint: spec.kindHint || (spec.url.match(/\.pkg$/i) ? 'pkg' : 'dmg') };
  }
  if (spec.kind === 'github') {
    const releasesUrl = `https://api.github.com/repos/${spec.owner}/${spec.repo}/releases/latest`;
    const data = await httpGetJson(releasesUrl);
    const assets = (data && data.assets) || [];
    const pick =
      assets.find(a => spec.assetMatch.test(a.name || '')) ||
      assets.find(a => spec.assetFallback && spec.assetFallback.test(a.name || ''));
    if (!pick) throw new Error(`no matching macOS asset in ${spec.owner}/${spec.repo}`);
    return {
      url: pick.browser_download_url,
      kindHint: pick.name.match(/\.pkg$/i) ? 'pkg' : 'dmg',
    };
  }
  throw new Error(`unknown installer kind for '${pluginId}'`);
}

// One-shot JSON GET with GitHub-friendly headers. No auth needed for public
// releases; we're well under the anonymous rate limit for a per-user flow.
function httpGetJson(url) {
  return new Promise((resolve, reject) => {
    const https = require('https');
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Nasty-DAW-Installer/1.0',
        'Accept': 'application/vnd.github+json',
      },
    }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return httpGetJson(res.headers.location).then(resolve, reject);
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`GET ${url} → HTTP ${res.statusCode}`));
      }
      let buf = '';
      res.on('data', d => buf += d);
      res.on('end', () => {
        try { resolve(JSON.parse(buf)); }
        catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => req.destroy(new Error('timeout')));
  });
}

// Streaming download with progress reporting. Follows redirects (GitHub
// asset URLs redirect to CDN). Writes to `destPath`. Calls `onProgress` with
// { bytes, total } roughly every 128 KB.
function downloadFile(url, destPath, onProgress) {
  return new Promise((resolve, reject) => {
    const https = require('https');
    const req = https.get(url, {
      headers: { 'User-Agent': 'Nasty-DAW-Installer/1.0' },
    }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return downloadFile(res.headers.location, destPath, onProgress).then(resolve, reject);
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`GET ${url} → HTTP ${res.statusCode}`));
      }
      const total = parseInt(res.headers['content-length'] || '0', 10) || 0;
      let bytes = 0, lastReported = 0;
      const out = fs.createWriteStream(destPath);
      res.on('data', chunk => {
        bytes += chunk.length;
        if (onProgress && bytes - lastReported > 128 * 1024) {
          lastReported = bytes;
          onProgress({ bytes, total });
        }
      });
      res.pipe(out);
      out.on('finish', () => {
        out.close(() => {
          if (onProgress) onProgress({ bytes, total });
          resolve({ bytes, total });
        });
      });
      out.on('error', reject);
    });
    req.on('error', reject);
    req.setTimeout(120000, () => req.destroy(new Error('timeout')));
  });
}

// Run a .pkg installer at user scope (no sudo). We target the current user's
// home directory so plugins land in ~/Library/Audio/Plug-Ins/*, which macOS
// treats as a valid Audio Units search path for the user.
function runPkgInstaller(pkgPath) {
  return new Promise((resolve, reject) => {
    const proc = spawn('installer', ['-pkg', pkgPath, '-target', 'CurrentUserHomeDirectory']);
    let stderr = '';
    proc.stderr.on('data', d => stderr += d);
    proc.on('close', code => {
      if (code === 0) resolve();
      else reject(new Error(`installer exit ${code}: ${stderr.trim()}`));
    });
    proc.on('error', reject);
  });
}

// Mount a .dmg, find the first .pkg inside, run installer on it, then
// detach. Handles the common OSS shape (Dexed, Surge XT, Sfizz all ship
// .pkg files inside a .dmg wrapper).
async function installFromDmg(dmgPath) {
  const { promisify } = require('util');
  const execFile = promisify(require('child_process').execFile);
  // hdiutil attach -nobrowse -mountrandom /tmp gives us a stable mountpoint
  // that won't clash with a user drag-mounted copy.
  const { stdout } = await execFile('hdiutil', [
    'attach', dmgPath, '-nobrowse', '-mountrandom', '/tmp',
  ]);
  // Last non-empty line's whitespace-split last field is the mountpoint.
  const lines = stdout.trim().split('\n').map(l => l.trim()).filter(Boolean);
  const mountLine = lines[lines.length - 1] || '';
  const mount = mountLine.split(/\s+/).pop();
  if (!mount || !mount.startsWith('/')) {
    throw new Error(`could not parse hdiutil mountpoint from: ${stdout}`);
  }
  try {
    const files = fs.readdirSync(mount);
    const pkg = files.find(f => f.toLowerCase().endsWith('.pkg'));
    if (!pkg) {
      // Some DMGs contain drag-install .vst3/.component bundles instead of a
      // .pkg. Fall back to copying those to the user plug-in folders.
      const homeDir = require('os').homedir();
      const vst3Dir = path.join(homeDir, 'Library', 'Audio', 'Plug-Ins', 'VST3');
      const auDir   = path.join(homeDir, 'Library', 'Audio', 'Plug-Ins', 'Components');
      fs.mkdirSync(vst3Dir, { recursive: true });
      fs.mkdirSync(auDir,   { recursive: true });
      let copied = 0;
      for (const f of files) {
        const src = path.join(mount, f);
        if (f.endsWith('.vst3')) { fs.cpSync(src, path.join(vst3Dir, f), { recursive: true }); copied++; }
        else if (f.endsWith('.component')) { fs.cpSync(src, path.join(auDir, f), { recursive: true }); copied++; }
      }
      if (copied === 0) throw new Error(`.dmg had neither .pkg nor drag-install bundles: ${files.join(', ')}`);
    } else {
      await runPkgInstaller(path.join(mount, pkg));
    }
  } finally {
    try { await execFile('hdiutil', ['detach', mount, '-force']); } catch (e) { /* best-effort */ }
  }
}

// Full flow: resolve URL → download → install → report progress. Renderer
// awaits the promise for terminal success/failure, but subscribes via
// `install-progress` events for per-plugin status.
ipcMain.handle('install-plugin-auto', async (evt, pluginId) => {
  const emit = (payload) => {
    if (evt.sender && !evt.sender.isDestroyed()) {
      evt.sender.send('install-progress', { pluginId, ...payload });
    }
  };
  try {
    if (!isAutoInstallable(pluginId)) {
      throw new Error(`plugin '${pluginId}' is not registered for auto-install`);
    }
    emit({ status: 'resolving' });
    const { url, kindHint } = await resolveInstallerUrl(pluginId);
    emit({ status: 'downloading', percent: 0 });
    const tmp = path.join(require('os').tmpdir(),
      `nasty-install-${pluginId}-${Date.now()}.${kindHint}`);
    await downloadFile(url, tmp, ({ bytes, total }) => {
      const percent = total ? Math.round(bytes / total * 100) : null;
      emit({ status: 'downloading', percent, bytes, total });
    });
    emit({ status: 'installing' });
    if (kindHint === 'pkg') {
      await runPkgInstaller(tmp);
    } else {
      await installFromDmg(tmp);
    }
    try { fs.unlinkSync(tmp); } catch (e) { /* ignore cleanup errors */ }
    emit({ status: 'done' });
    return { ok: true };
  } catch (e) {
    const msg = String(e && e.message || e);
    emit({ status: 'error', error: msg });
    return { ok: false, error: msg };
  }
});

// Renderer asks for the auto-installable set so the bundle UI knows which
// items should route through auto-install vs vendor tabs.
ipcMain.handle('list-auto-installable-plugins', () => Object.keys(OSS_INSTALLERS));


// Renderer reads this to send the SF2 path along with GM channel creation.
ipcMain.handle('nasty-sf2-path', () => {
  const devInstruments  = path.join(__dirname, '..', 'audio-engine', 'bundled-instruments');
  const prodInstruments = path.join(process.resourcesPath || '', 'bundled-instruments');
  const dir = fs.existsSync(devInstruments) ? devInstruments
            : fs.existsSync(prodInstruments) ? prodInstruments : null;
  return dir ? path.join(dir, 'GeneralUser.sf2') : '';
});

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

  // Tell the audio engine when Nasty gains/loses focus so it can lower
  // plugin windows from floating to normal level — otherwise they sit on
  // top of Chrome/Slack when the user Cmd+Tabs away.
  const sendFocus = (focused) => {
    if (audioEngineProc && audioEngineProc.stdin.writable) {
      try { audioEngineProc.stdin.write(JSON.stringify({ cmd: 'nasty_focus', focused }) + '\n'); } catch {}
    }
  };
  mainWindow.on('focus', () => sendFocus(true));
  mainWindow.on('blur',  () => sendFocus(false));
  // Surface renderer errors in the terminal so silent crashes are visible.
  mainWindow.webContents.on('render-process-gone', (_e, d) => console.error('[nasty] renderer gone:', d));
  mainWindow.webContents.on('console-message', (_e, level, msg, line, src) => {
    if (level >= 2) console.error('[renderer]', src + ':' + line, msg);
  });
  // Show even if ready-to-show never fires (renderer crash before then).
  setTimeout(() => { if (mainWindow && !mainWindow.isVisible()) mainWindow.show(); }, 2000);

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
        // Clears the onboarded flag and re-shows the welcome flow. Testing
        // aid for the maintainer — lets Brendan experience the fresh-install
        // path without wiping his real Nasty install.
        { label: 'Reset onboarding…', click: () => sendCmd('reset-onboarding') },
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
  seedBundledInstruments();
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
