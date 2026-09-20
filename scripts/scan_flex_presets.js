#!/usr/bin/env node
// Scan the user's FLEX preset library and emit a slim JSON index.
//
// FLEX installs its expansion packs at ~/Documents/Image-Line/FLEX/Packs/,
// where each pack is a plain-text `.preset` file — one preset name per
// line. Nasty reads these names so Claude can answer "what bass sounds do
// I have in FLEX?" against the user's ACTUAL library, and later trigger
// specific presets by name.
//
// Runs standalone (for testing/dry-runs) and is also imported by main.js.

const fs = require('fs');
const path = require('path');
const os = require('os');

function findFlexPacksDir() {
  const home = os.homedir();
  const candidates = [
    path.join(home, 'Documents', 'Image-Line', 'FLEX', 'Packs'),
    path.join('/Users/Shared', 'Image-Line', 'FLEX', 'Packs'),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

function readPresetFile(packFile) {
  let raw;
  try {
    raw = fs.readFileSync(packFile, 'utf8');
  } catch (_) {
    return [];
  }
  return raw
    .split(/\r?\n/)
    .map(s => s.trim())
    .filter(Boolean);
}

function scanFlexPresets(overrideDir) {
  const root = overrideDir || findFlexPacksDir();
  if (!root) return { root: null, packs: [], totalPresets: 0 };
  let entries;
  try {
    entries = fs.readdirSync(root, { withFileTypes: true });
  } catch (_) {
    return { root, packs: [], totalPresets: 0 };
  }
  const packs = [];
  let total = 0;
  for (const ent of entries) {
    if (!ent.isFile()) continue;
    if (!ent.name.endsWith('.preset')) continue;
    // Skip favorite.ini/recent.ini style user state — they're .ini, not
    // .preset, but be defensive.
    if (ent.name === 'favorite.preset' || ent.name === 'recent.preset') continue;
    // FLEX ships a bare `.preset` file (no basename) for the factory
    // library. Label it so it doesn't come through as empty.
    const rawName = ent.name.replace(/\.preset$/, '');
    const packName = rawName || 'FLEX Factory';
    const filePath = path.join(root, ent.name);
    const presets = readPresetFile(filePath);
    if (presets.length === 0) continue;
    packs.push({ pack: packName, presets });
    total += presets.length;
  }
  packs.sort((a, b) => b.presets.length - a.presets.length);
  return { root, packs, totalPresets: total };
}

module.exports = { scanFlexPresets, findFlexPacksDir };

// Standalone entry: node scripts/scan_flex_presets.js [--full]
if (require.main === module) {
  const args = process.argv.slice(2);
  const full = args.includes('--full');
  const result = scanFlexPresets();
  if (!result.root) {
    console.error('No FLEX Packs directory found.');
    process.exit(1);
  }
  console.error(`[flex] scanned ${result.packs.length} packs, ${result.totalPresets} presets from ${result.root}`);
  if (full) {
    process.stdout.write(JSON.stringify(result, null, 2));
  } else {
    const summary = {
      root: result.root,
      packCount: result.packs.length,
      totalPresets: result.totalPresets,
      packs: result.packs.map(p => ({ pack: p.pack, count: p.presets.length })),
    };
    process.stdout.write(JSON.stringify(summary, null, 2));
  }
}
