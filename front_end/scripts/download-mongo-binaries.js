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

// ─── Configuration ────────────────────────────────────────────────────────────

const binDir = path.join(os.homedir(), '.nlm', 'bin');

const BINARIES = [
  {
    binaryName: 'mongod',
    binaryPath: path.join(binDir, 'mongod'),
    url: 'https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2204-8.0.19.tgz',
    // SHA256 from: curl https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2204-8.0.19.tgz.sha256
    sha256: 'a41f8cde7b67b0fcf13353ca40b890094a4bf76a0486877e05ec17d19e19b807',
    extractPattern: '*/bin/mongod',
    tmpTarball: path.join(binDir, 'mongod.tgz.tmp'),
    label: 'MongoDB 8.0.19',
  },
  {
    binaryName: 'mongodump',
    binaryPath: path.join(binDir, 'mongodump'),
    url: 'https://fastdl.mongodb.org/tools/db/mongodb-database-tools-ubuntu2204-x86_64-100.14.0.tgz',
    // SHA256 from: curl https://fastdl.mongodb.org/tools/db/mongodb-database-tools-ubuntu2204-x86_64-100.14.0.tgz.sha256
    sha256: '4104998bda784a0cb16fc2e06d9c21645516d72c4fb481c9b103f1e0a8458fc0',
    extractPattern: '*/bin/mongodump',
    tmpTarball: path.join(binDir, 'mongodump.tgz.tmp'),
    label: 'MongoDB Database Tools 100.14.0',
  },
];

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

/** Extract a single binary from a tarball using system tar. */
function extract(tarball, destDir, pattern) {
  return new Promise((resolve, reject) => {
    execFile(
      'tar',
      [
        '--strip-components=2',
        '-xzf', tarball,
        '-C', destDir,
        '--wildcards', pattern,
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

/** Download, verify, extract, chmod, and clean up one binary. */
async function installBinary({ binaryName, binaryPath, url, sha256, extractPattern, tmpTarball, label }) {
  console.log(`Downloading ${label} (${binaryName})...`);

  // Download tarball
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

  // Extract binary
  console.log(`  Extracting ${binaryName}...`);
  await extract(tmpTarball, binDir, extractPattern);

  // Set executable bit
  fs.chmodSync(binaryPath, 0o755);

  // Clean up temp tarball
  fs.unlinkSync(tmpTarball);

  console.log(`  ${binaryName} installed at: ${binaryPath}`);
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const missing = BINARIES.filter(b => !fs.existsSync(b.binaryPath));

  if (missing.length === 0) {
    console.log('mongod and mongodump already present — skipping download.');
    return;
  }

  const present = BINARIES.filter(b => fs.existsSync(b.binaryPath));
  for (const b of present) {
    console.log(`${b.binaryName} already present — skipping.`);
  }

  // Ensure destination directory exists (tar -C requires it)
  fs.mkdirSync(binDir, { recursive: true });

  for (const binary of missing) {
    await installBinary(binary);
  }
}

main().catch(err => {
  console.error('download-mongo-binaries failed:', err.message);
  process.exit(1);
});
