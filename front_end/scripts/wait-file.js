const { existsSync, watch, mkdirSync } = require('fs');
const { dirname } = require('path');

const target = process.argv[2];
if (!target) { console.error('usage: node wait-file.js <path>'); process.exit(1); }
if (existsSync(target)) process.exit(0);

const dir = dirname(target);
mkdirSync(dir, { recursive: true });

const watcher = watch(dir, () => {
  // No `name &&` guard: on Windows, ReadDirectoryChangesW can fire with
  // name === null for non-specific directory events — guarding on name
  // causes a silent hang when the file appears via such an event.
  if (existsSync(target)) { watcher.close(); process.exit(0); }
});

// Close the TOCTOU window: file may have arrived between the initial
// existsSync check above and watch() registration.
if (existsSync(target)) { watcher.close(); process.exit(0); }

// Timeout guard: exits nonzero if webpack crashes and never writes the file.
setTimeout(() => {
  watcher.close();
  console.error(`wait-file.js: timed out waiting for ${target}`);
  process.exit(1);
}, 120_000);
