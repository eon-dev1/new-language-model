// launch-electron.js
// Starts Electron (replacing a bare `electron dist/main/main.js`) so that a Linux
// chrome-sandbox permission failure can be explained with the fix commands.
//
// Why a wrapper: the "SUID sandbox helper ... not configured correctly" abort comes from
// Electron's native code before any app JS runs, so nothing inside src/main can catch it.
// Only the parent process can see that Electron died and add guidance.
//
// Usage: node scripts/launch-electron.js [electron args...]  (default: dist/main/main.js)

'use strict';

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

// Electron requires chrome-sandbox to be root-owned with the setuid bit and mode 4755.
const REQUIRED_SANDBOX_MODE = 0o4755;

/**
 * Returns the commands that fix chrome-sandbox, or null if its ownership/mode are
 * already correct (so the crash had some other cause and we must not misdirect the user).
 * `stats` is the fs.Stats of the file.
 */
function sandboxFixCommands(sandboxPath, stats) {
  const correct = stats.uid === 0 && (stats.mode & 0o7777) === REQUIRED_SANDBOX_MODE;
  if (correct) return null;
  return [
    `sudo chown root:root ${sandboxPath}`,
    `sudo chmod 4755 ${sandboxPath}`,
  ];
}

// Only an abnormal exit is inspected: with a user-namespace sandbox (e.g. when launched
// from VS Code's terminal on Ubuntu 24.04) Electron runs fine despite wrong ownership,
// so warning on every launch would be noise.
function reportSandboxProblem(electronPath) {
  if (process.platform !== 'linux') return;
  const sandboxPath = path.join(path.dirname(electronPath), 'chrome-sandbox');
  let stats;
  try {
    stats = fs.statSync(sandboxPath);
  } catch {
    return;
  }
  const commands = sandboxFixCommands(sandboxPath, stats);
  if (!commands) return;
  console.error(`
Electron exited abnormally and ${sandboxPath}
is not root-owned with mode 4755. If the error above mentions the SUID sandbox, run:

  ${commands.join('\n  ')}

(Re-run after reinstalling or upgrading Electron, which resets the ownership.)
See README.md, "Linux: Electron aborts on launch with a chrome-sandbox SUID error".
`);
}

function main() {
  // Requiring 'electron' resolves the binary path, downloading it first if missing.
  const electronPath = require('electron');
  const args = process.argv.length > 2 ? process.argv.slice(2) : ['dist/main/main.js'];

  const child = spawn(electronPath, args, { stdio: 'inherit', windowsHide: false });
  let childClosed = false;

  child.on('error', (err) => {
    console.error(`Failed to start Electron: ${err.message}`);
    process.exit(1);
  });

  child.on('close', (code, signal) => {
    childClosed = true;
    if (code === 0) process.exit(0);
    if (code === null) console.error(electronPath, 'exited with signal', signal);
    reportSandboxProblem(electronPath);
    process.exit(code === null ? 1 : code);
  });

  // Forward termination so Ctrl+C in the terminal also stops Electron.
  for (const signal of ['SIGINT', 'SIGTERM', 'SIGUSR2']) {
    process.on(signal, () => {
      if (!childClosed) child.kill(signal);
    });
  }
}

if (require.main === module) {
  main();
}

module.exports = { sandboxFixCommands };
