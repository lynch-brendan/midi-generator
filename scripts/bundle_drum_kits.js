#!/usr/bin/env node
// Copy usable drum kits from the repo `Drum kits/` folder into
// `audio-engine/bundled-instruments/drum-kits/` so electron-builder ships
// them inside the .dmg. Uses the SAME auto-map logic as electron/main.js
// so "usable" here means "the same auto-map that runs at Nasty boot on
// the user's machine finds at least a kick or snare."
//
// Numeric-only kits ("MaxV - 01.wav" etc.) can't be classified without
// listening — they're skipped so the AI never wastes a load call on
// something that would come back empty.
//
// Idempotent: destination folders are removed and re-created each run so
// renaming a source file or fixing the auto-map heuristics flows through
// cleanly on the next bundle.

const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, '..', 'Drum kits');
const DEST = path.join(__dirname, '..', 'audio-engine', 'bundled-instruments', 'drum-kits');

function autoMapKit(kitDir) {
  let files;
  try {
    files = fs.readdirSync(kitDir)
      .filter(f => f.toLowerCase().endsWith('.wav'))
      .sort();
  } catch (_) { return {}; }
  const firstMatch = (...keywords) => files.find(f => {
    const lower = f.toLowerCase();
    return keywords.some(kw => lower.includes(kw));
  }) || null;

  const kick = firstMatch('kick_hard', 'kick_med')
            || firstMatch('kick', 'bd', 'bass drum', 'bassdrum', 'bsdrum', 'kick1', 'kick_1')
            || firstMatch('bass');
  const snare = firstMatch('snare_hard', 'snare_med')
             || firstMatch('snare', 'sd ', 'snr', 'sn1', 'sn_1', '_sn.', '_sn_', '-sn-', '-sn.', 'esnare');
  const clap  = firstMatch('clap', 'clp');
  let chh = firstMatch('closed hat', 'closed_hat', 'closed-hat', 'hihat closed',
                        'hat_c', 'hat-c', 'hat c', 'hh_c', 'hh-c', 'hh c',
                        'hh cl', 'hh_cl', 'hh-cl', 'hihat_c', 'hihat-c', 'hihat c',
                        'hi-hat_c', 'hi-hat-c', 'hi-hat c',
                        'chh', 'clsd', 'closed', 'hat_closed', 'hat-closed');
  if (!chh) chh = files.find(f => {
    const lower = f.toLowerCase();
    return (lower.includes('hat') || lower.includes('hh') || lower.includes('hihat'))
        && !lower.includes('open') && !lower.includes('oh ') && !lower.includes('op ')
        && !lower.includes(' op') && !lower.includes('_op');
  }) || null;
  return { kick, snare, clap, chh };
}

function copyKit(name) {
  const src = path.join(SRC, name);
  const dst = path.join(DEST, name);
  // Fresh copy each run — see header for why.
  if (fs.existsSync(dst)) fs.rmSync(dst, { recursive: true, force: true });
  fs.mkdirSync(dst, { recursive: true });
  // Only copy .wav files; skip Ableton's .asd sidecars and .lnk shortcuts
  // that make the .dmg bigger for zero user value.
  let n = 0;
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (!entry.isFile()) continue;
    if (!entry.name.toLowerCase().endsWith('.wav')) continue;
    fs.copyFileSync(path.join(src, entry.name), path.join(dst, entry.name));
    n++;
  }
  return n;
}

function main() {
  if (!fs.existsSync(SRC)) {
    console.error('source not found:', SRC);
    process.exit(1);
  }
  if (fs.existsSync(DEST)) {
    console.log('wiping existing', DEST);
    fs.rmSync(DEST, { recursive: true, force: true });
  }
  fs.mkdirSync(DEST, { recursive: true });

  const kitNames = fs.readdirSync(SRC, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => d.name)
    .sort();

  let bundled = 0, skipped = 0, totalWavs = 0;
  const skippedNames = [];
  for (const name of kitNames) {
    const map = autoMapKit(path.join(SRC, name));
    // "Usable" = has at least a kick or snare, matching main.js's runtime filter.
    if (!map.kick && !map.snare) {
      skipped++;
      skippedNames.push(name);
      continue;
    }
    const wavs = copyKit(name);
    totalWavs += wavs;
    bundled++;
  }

  console.log(`bundled ${bundled} kits (${totalWavs} wavs total)`);
  console.log(`skipped ${skipped} unmappable kits`);
  if (skipped) {
    console.log('skipped:', skippedNames.slice(0, 10).join(', '),
                skipped > 10 ? `… (+${skipped - 10} more)` : '');
  }
}

main();
