// setup.js
// One-command fresh-machine setup: npm install, Python environment (uv sync),
// MongoDB binaries, and the MongoDB credential.
// Run via: npm run setup (from front_end/)

'use strict';

const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFileSync } = require('child_process');

const scriptDir = __dirname;
const frontEndDir = path.join(scriptDir, '..');
const repoRoot = path.join(scriptDir, '..', '..');
const backEndDir = path.join(repoRoot, 'back_end');

// Official uv on Windows is uv.exe. execFileSync without a shell does not apply
// PATHEXT, so the extension must be spelled out; a shell would only add a quoting surface.
const uvCmd = process.platform === 'win32' ? 'uv.exe' : 'uv';

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

  // uv downloads the Python version pinned in .python-version itself, so no system
  // Python is needed — only uv.
  let uvVersion;
  try {
    uvVersion = execFileSync(uvCmd, ['--version'], {
      encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 5000,
    }).trim();
  } catch {
    throw new Error('uv is required and was not found on PATH. Install it from https://docs.astral.sh/uv/ and re-run.');
  }
  console.log(`  ${uvVersion} detected.`);

  console.log('  Plan: npm install -> uv sync -> MongoDB binaries -> MongoDB credential -> git hooks.');
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

function stage2UvSync() {
  console.log('Stage 2: uv sync');
  // Runs every time, not only on first setup: a skip-if-present check would leave the
  // environment behind uv.lock after a pull. A warm uv cache makes a no-op sync fast.
  // uv honours UV_PROJECT_ENVIRONMENT, so the devcontainer's venv path needs no branch here.
  execFileSync(uvCmd, ['sync'], { cwd: repoRoot, stdio: 'inherit' });
}

function stage3MongoBinaries() {
  console.log('Stage 3: MongoDB binaries');
  execFileSync(process.execPath, [path.join(scriptDir, 'download-mongo-binaries.js')], {
    cwd: frontEndDir, stdio: 'inherit',
  });
}

function stage4MongoCredential() {
  console.log('Stage 4: MongoDB credential');
  execFileSync(uvCmd, ['run', '--directory', backEndDir, 'python', '-m', 'db_connector.setup_auth'], {
    stdio: 'inherit',
  });
}

function stage5GitHooks() {
  console.log('Stage 5: Git hooks');
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

function stage6Checklist() {
  console.log(`
Setup complete.

  MongoDB credential: created at ${path.join(os.homedir(), '.nlm', 'mongodb_credentials.env')}
  (Optional) LLM API key: Settings > Chat Config in-app, or edit
             ${path.join(os.homedir(), '.nlm', 'chat_config.json')} after first launch.

Then: cd front_end && npm run dev
`);
}

function main() {
  stage0Preflight();
  stage1NpmInstall();
  stage2UvSync();
  stage3MongoBinaries();
  stage4MongoCredential();
  stage5GitHooks();
  stage6Checklist();
}

if (require.main === module) {
  try {
    main();
  } catch (err) {
    console.error(`Setup failed: ${err.message}`);
    process.exit(1);
  }
}

module.exports = { main };
