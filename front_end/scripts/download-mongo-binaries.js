// download-mongo-binaries.js
// Downloads mongod and mongodump binaries to ~/.nlm/bin/.
// Run via: node scripts/download-mongo-binaries.js
// Idempotent: each binary is checked independently; only missing ones are downloaded.

'use strict';

const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { execFile } = require('child_process');
const { promisify } = require('util');

const execFileP = promisify(execFile);

// ─── Configuration ────────────────────────────────────────────────────────────

const binDir = path.join(os.homedir(), '.nlm', 'bin');

const LINUX_BINARIES = [
  {
    binaryName: 'mongod',
    binaryPath: path.join(binDir, 'mongod'),
    url: 'https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2204-8.0.19.tgz',
    // SHA256 from: curl https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2204-8.0.19.tgz.sha256
    sha256: 'a41f8cde7b67b0fcf13353ca40b890094a4bf76a0486877e05ec17d19e19b807',
    tmpTarball: path.join(binDir, 'mongod.tgz.tmp'),
    label: 'MongoDB 8.0.19',
  },
  {
    binaryName: 'mongodump',
    binaryPath: path.join(binDir, 'mongodump'),
    url: 'https://fastdl.mongodb.org/tools/db/mongodb-database-tools-ubuntu2204-x86_64-100.14.0.tgz',
    // SHA256 from: curl https://fastdl.mongodb.org/tools/db/mongodb-database-tools-ubuntu2204-x86_64-100.14.0.tgz.sha256
    sha256: '4104998bda784a0cb16fc2e06d9c21645516d72c4fb481c9b103f1e0a8458fc0',
    tmpTarball: path.join(binDir, 'mongodump.tgz.tmp'),
    label: 'MongoDB Database Tools 100.14.0',
  },
];

const WINDOWS_BINARIES = [
  {
    binaryName: 'mongod.exe',
    binaryPath: path.join(binDir, 'mongod.exe'),
    url: 'https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-8.0.19.zip',
    // SHA256 from: curl https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-8.0.19.zip.sha256
    sha256: '93360efdae513b62feb5f3f529f17639c21173fd47ffeb1985c435f6e6052b18',
    tmpTarball: path.join(binDir, 'mongod.tmp.zip'),
    label: 'MongoDB 8.0.19 (Windows)',
  },
  {
    binaryName: 'mongodump.exe',
    binaryPath: path.join(binDir, 'mongodump.exe'),
    url: 'https://fastdl.mongodb.org/tools/db/mongodb-database-tools-windows-x86_64-100.14.0.zip',
    // SHA256 from: certutil -hashfile mdbtools.zip SHA256
    sha256: '3ba13d9e504b1bde9b0621471a68c57f47954d1583772e40dd97e174b822cc99',
    tmpTarball: path.join(binDir, 'mongodump.tmp.zip'),
    label: 'MongoDB Database Tools 100.14.0 (Windows)',
  },
];

function getBinaries(platform = process.platform) {
  switch (platform) {
    case 'win32': return WINDOWS_BINARIES;
    case 'linux': return LINUX_BINARIES;
    case 'darwin':
      throw new Error('macOS support not yet implemented. See __plans__/windows-compat.md.');
    default:
      throw new Error(`Unsupported platform: ${platform}`);
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Compute SHA256 hex digest of a file. */
function sha256File(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    const stream = fs.createReadStream(filePath);
    stream.on('data', chunk => hash.update(chunk));
    stream.on('end', () => resolve(hash.digest('hex')));
    stream.on('error', reject);
  });
}

/** Download a URL to a local file path. */
function download(url, dest, label) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    let totalBytes = 0;
    let receivedBytes = 0;

    function get(urlStr) {
      https.get(urlStr, res => {
        if (res.statusCode === 301 || res.statusCode === 302) {
          get(res.headers.location);
          return;
        }
        if (res.statusCode !== 200) {
          file.close();
          reject(new Error(`HTTP ${res.statusCode} downloading ${urlStr}`));
          return;
        }
        totalBytes = parseInt(res.headers['content-length'] || '0', 10);
        res.on('data', chunk => {
          receivedBytes += chunk.length;
          if (totalBytes > 0) {
            const pct = ((receivedBytes / totalBytes) * 100).toFixed(1);
            process.stdout.write(`\r  Downloading ${label}... ${pct}%`);
          }
        });
        res.pipe(file);
        file.on('finish', () => {
          file.close();
          if (totalBytes > 0) process.stdout.write('\n');
          resolve();
        });
        file.on('error', reject);
      }).on('error', reject);
    }
    get(url);
  });
}

/** Extract a single binary from a .tgz using system tar (Linux). */
function extractLinux(archive, destDir, binaryName) {
  return new Promise((resolve, reject) => {
    execFile(
      'tar',
      [
        '--strip-components=2',
        '-xzf', archive,
        '-C', destDir,
        '--wildcards', `*/bin/${binaryName}`,
      ],
      (err, _stdout, stderr) => {
        if (err) {
          if (err.code === 'ENOENT') {
            reject(new Error('tar not found — required for extraction on Linux'));
          } else {
            reject(new Error(`tar failed: ${stderr || err.message}`));
          }
          return;
        }
        resolve();
      }
    );
  });
}

/** Extract a single binary from a .zip using PowerShell (Windows). */
async function extractWindows(archive, destDir, binaryName) {
  // Escape single quotes so paths with apostrophes (e.g. user "O'Brien") don't break PS syntax.
  const safePath = s => s.replace(/'/g, "''");
  const tmpDir = path.join(destDir, `${binaryName}.extract.tmp`);

  try {
    // Step 1: Expand the zip into a temp directory.
    // -LiteralPath disables glob expansion on the archive path.
    // -NonInteractive prevents any hanging prompt.
    // -ErrorAction Stop turns non-terminating errors into terminating ones.
    await execFileP('powershell.exe', [
      '-NoProfile', '-NonInteractive', '-Command',
      `Expand-Archive -LiteralPath '${safePath(archive)}' -DestinationPath '${safePath(tmpDir)}' -Force -ErrorAction Stop`,
    ]);

    // Step 2: Walk tmpDir and find the binary by exact basename.
    // Matching by name (not extension) avoids picking up mongos.exe, mongorestore.exe, etc.
    function findFile(dir) {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          const found = findFile(fullPath);
          if (found) return found;
        } else if (entry.name === binaryName) {
          return fullPath;
        }
      }
      return null;
    }

    const foundPath = findFile(tmpDir);
    if (!foundPath) {
      throw new Error(`Binary '${binaryName}' not found inside extracted archive`);
    }

    // Step 3: Move binary to destination.
    fs.renameSync(foundPath, path.join(destDir, binaryName));
  } finally {
    // Step 4: Always remove the extraction tree, success or failure.
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

/**
 * Dispatch extraction by platform.
 * extractLinux uses GNU tar with --wildcards.
 * extractWindows uses PowerShell Expand-Archive + recursive walk.
 */
function extract(platform, archive, destDir, binaryName) {
  switch (platform) {
    case 'linux': return extractLinux(archive, destDir, binaryName);
    case 'win32': return extractWindows(archive, destDir, binaryName);
    case 'darwin':
      throw new Error('macOS extraction not yet implemented. See __plans__/windows-compat.md.');
    default:
      throw new Error(`Unsupported platform for extraction: ${platform}`);
  }
}

/** Download, verify, extract, chmod, and clean up one binary. */
async function installBinary({ binaryName, binaryPath, url, sha256, tmpTarball, label }) {
  if (!sha256 || sha256.length !== 64) {
    throw new Error(`SHA256 not configured for ${binaryName}. Fill in WINDOWS_BINARIES before shipping.`);
  }

  console.log(`Downloading ${label} (${binaryName})...`);

  // Download archive
  await download(url, tmpTarball, label);

  // Verify SHA256
  const actual = await sha256File(tmpTarball);
  if (actual !== sha256) {
    fs.unlinkSync(tmpTarball);
    throw new Error(
      `SHA256 mismatch for ${binaryName} tarball.\n` +
      `  expected: ${sha256}\n` +
      `  actual:   ${actual}\n` +
      'Do NOT use this binary. The download may be corrupt or tampered with.'
    );
  }
  console.log(`  SHA256 verified.`);

  // Extract binary — always clean up the archive even on extraction failure
  console.log(`  Extracting ${binaryName}...`);
  try {
    await extract(process.platform, tmpTarball, binDir, binaryName);
  } finally {
    fs.rmSync(tmpTarball, { force: true });
  }

  // Set executable bit (no-op on Windows)
  fs.chmodSync(binaryPath, 0o755);

  console.log(`  ${binaryName} installed at: ${binaryPath}`);
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const binaries = getBinaries(process.platform);
  const missing = binaries.filter(b => !fs.existsSync(b.binaryPath));

  if (missing.length === 0) {
    console.log('mongod and mongodump already present — skipping download.');
    return;
  }

  const present = binaries.filter(b => fs.existsSync(b.binaryPath));
  for (const b of present) {
    console.log(`${b.binaryName} already present — skipping.`);
  }

  // Ensure destination directory exists
  fs.mkdirSync(binDir, { recursive: true });

  for (const binary of missing) {
    await installBinary(binary);
  }
}

if (require.main === module) {
  main().catch(err => {
    console.error('download-mongo-binaries failed:', err.message);
    process.exit(1);
  });
}

module.exports = { getBinaries, main };
