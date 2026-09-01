// setup.js
// One-command fresh-machine setup: npm install, Python venv, pip install,
// MongoDB binaries, and the MongoDB credential.
// Run via: npm run setup (from front_end/)

'use strict';

const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFileSync } = require('child_process');

const scriptDir = __dirname;
const frontEndDir = path.join(scriptDir, '..');
const backEndDir = path.join(scriptDir, '..', '..', 'back_end');

function detectPython() {
  const candidates = process.platform === 'win32'
    ? [['python', []], ['py', ['-3']], ['python3', []]]
    : [['python3', []], ['python', []]];

  for (const [cmd, prefix] of candidates) {
    try {
      const out = execFileSync(cmd, [...prefix, '--version'], {
        encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 3000,
      });
      const m = /Python (\d+)\.(\d+)/.exec(out);
      if (m && (+m[1] > 3 || (+m[1] === 3 && +m[2] >= 10))) {
        return { cmd, prefix, version: `${m[1]}.${m[2]}` };
      }
    } catch { /* try next candidate */ }
  }
  return null;
}

function venvPythonPath() {
  return process.platform === 'win32'
    ? path.join(backEndDir, 'nlm_backend_venv', 'Scripts', 'python.exe')
    : path.join(backEndDir, 'nlm_backend_venv', 'bin', 'python');
}

function stage0Preflight() {
  console.log('Stage 0: Preflight');

  if (process.platform === 'darwin') {
    throw new Error('macOS is not yet supported by the automated setup. See README.md for the manual path.');
  }
  if (!['win32', 'linux'].includes(process.platform)) {
    throw new Error(`Unsupported platform: ${process.platform}. See README.md for the manual path.`);
  }
  if (process.platform === 'win32') {
    console.log('  Windows: the automated path is unverified — see README.md if it fails partway.');
  }

  const [major] = process.versions.node.split('.').map(Number);
  if (major < 18) {
    throw new Error(`Node 18+ required (found ${process.versions.node}).`);
  }

  const python = detectPython();
  if (!python) {
    throw new Error("Python 3.10+ required. Install from python.org — on Windows check 'Add python.exe to PATH'.");
  }
  console.log(`  Python ${python.version} detected (${python.cmd}).`);

  console.log('  Plan: npm install -> Python venv -> pip install -> MongoDB binaries -> MongoDB credential -> git hooks.');
  return python;
}

function stage1NpmInstall() {
  console.log('Stage 1: npm install');
  if (fs.existsSync(path.join(frontEndDir, 'node_modules'))) {
    console.log('  node_modules/ already present — skipping.');
    return;
  }
  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  execFileSync(npmCmd, ['install'], {
    cwd: frontEndDir, stdio: 'inherit',
    shell: process.platform === 'win32',  // required for .cmd post-CVE-2024-27980
  });
}

function stage2Venv(python) {
  console.log('Stage 2: Python venv');
  const venvDir = path.join(backEndDir, 'nlm_backend_venv');
  const venvPython = venvPythonPath();

  if (fs.existsSync(venvPython)) {
    console.log('  nlm_backend_venv/ already exists — skipping.');
    return;
  }
  if (fs.existsSync(venvDir)) {
    throw new Error(
      `nlm_backend_venv/ exists but is incomplete (no ${path.relative(backEndDir, venvPython)}). ` +
      'Delete the directory and re-run setup.'
    );
  }

  execFileSync(python.cmd, [...python.prefix, '-m', 'venv', 'nlm_backend_venv'], {
    cwd: backEndDir, stdio: 'inherit',
  });
}

function stage3PipInstall() {
  console.log('Stage 3: pip install');
  execFileSync(venvPythonPath(), ['-m', 'pip', 'install', '-r', 'requirements.txt'], {
    cwd: backEndDir, stdio: 'inherit',
  });
}

function stage4MongoBinaries() {
  console.log('Stage 4: MongoDB binaries');
  execFileSync(process.execPath, [path.join(scriptDir, 'download-mongo-binaries.js')], {
    cwd: frontEndDir, stdio: 'inherit',
  });
}

function stage5MongoCredential() {
  console.log('Stage 5: MongoDB credential');
  execFileSync(venvPythonPath(), ['-m', 'db_connector.setup_auth'], {
    cwd: backEndDir, stdio: 'inherit',
  });
}

function stage6GitHooks() {
  console.log('Stage 6: Git hooks');
  const repoRoot = path.join(scriptDir, '..', '..');
  // Relative hooksPath is resolved by git against the working-tree root, and is
  // committed, so every clone shares .githooks/ once this runs. Idempotent.
  // Best-effort: a ZIP/tarball download is not a git repo, so `git config` would
  // throw — warn and skip rather than fail setup after the heavy stages succeeded.
  try {
    execFileSync('git', ['config', 'core.hooksPath', '.githooks'], {
      cwd: repoRoot, stdio: 'inherit',
    });
  } catch {
    // Fires for a non-git tree (archive download) OR git-not-installed (ENOENT);
    // the manual-command fallback covers both, so we don't distinguish.
    console.log('  Could not set git hooks (not a git repo, or git not installed) — skipping.');
    console.log('  In a real clone with git available, run: git config core.hooksPath .githooks');
    return;
  }
  try {
    execFileSync('trufflehog', ['--version'], { stdio: 'ignore' });
    console.log('  pre-commit secret scan wired; trufflehog present.');
  } catch {
    // Non-fatal: trufflehog is only needed at commit time, and the hook itself
    // hard-fails there with install instructions. Warn so it isn't a surprise.
    console.log('  pre-commit secret scan wired. WARNING: trufflehog not found — commits');
    console.log('  will be BLOCKED until it is installed:');
    console.log('  https://github.com/trufflesecurity/trufflehog#installation');
  }
}

function stage7Checklist() {
  console.log(`
Setup complete.

  MongoDB credential: created at ${path.join(os.homedir(), '.nlm', 'mongodb_credentials.env')}
  (Optional) LLM API key: Settings > Chat Config in-app, or edit
             ${path.join(os.homedir(), '.nlm', 'chat_config.json')} after first launch.

Then: cd front_end && npm run dev
`);
}

function main() {
  const python = stage0Preflight();
  stage1NpmInstall();
  stage2Venv(python);
  stage3PipInstall();
  stage4MongoBinaries();
  stage5MongoCredential();
  stage6GitHooks();
  stage7Checklist();
}

if (require.main === module) {
  try {
    main();
  } catch (err) {
    console.error(`Setup failed: ${err.message}`);
    process.exit(1);
  }
}

module.exports = { detectPython, venvPythonPath, main };
