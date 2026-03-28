// download-mongod.js
// Downloads the mongod binary for Linux x86_64 (Ubuntu 22.04+).
// Run via: node scripts/download-mongod.js
// Idempotent: skips download if binary already exists.

'use strict';

const https = require('https');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFile } = require('child_process');

// ─── Configuration ────────────────────────────────────────────────────────────

const TARBALL_URL =
  'https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2204-8.0.19.tgz';

// SHA256 of the tarball (not the extracted binary).
// Obtained from: curl https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2204-8.0.19.tgz.sha256
// This verifies the download is intact and matches the expected file.
const EXPECTED_SHA256 =
  'a41f8cde7b67b0fcf13353ca40b890094a4bf76a0486877e05ec17d19e19b807';

if (EXPECTED_SHA256 === '<paste hex digest here after first download>') {
  throw new Error(
    'Bootstrap required: set EXPECTED_SHA256 in scripts/download-mongod.js.\n' +
    'Run: curl https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2204-8.0.19.tgz.sha256'
  );
}

// Paths are resolved relative to this script's location (front_end/scripts/)
const binDir      = path.resolve(__dirname, '..', 'resources', 'bin');
const BINARY_PATH = path.join(binDir, 'mongod');
const tmpTarball  = path.join(binDir, 'mongod.tgz.tmp');

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
function download(url, dest) {
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
            process.stdout.write(`\r  Downloading mongod... ${pct}%`);
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

/** Extract mongod binary from tarball using system tar. */
function extract(tarball, destDir) {
  return new Promise((resolve, reject) => {
    execFile(
      'tar',
      [
        '--strip-components=2',
        '-xzf', tarball,
        '-C', destDir,
        '--wildcards', '*/bin/mongod',
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

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  // 1. If binary already exists → skip download (idempotent fast-path)
  if (fs.existsSync(BINARY_PATH)) {
    console.log('mongod binary already present — skipping download.');
    return;
  }

  console.log('Downloading MongoDB 8.0.19 binary for Linux x86_64 (Ubuntu 22.04+)...');

  // 2. Ensure destination directory exists (tar -C requires it)
  fs.mkdirSync(binDir, { recursive: true });

  // 3. Download tarball
  await download(TARBALL_URL, tmpTarball);

  // 4. Verify tarball SHA256 (catches corrupt/partial downloads and CDN tampering)
  const actual = await sha256File(tmpTarball);
  if (actual !== EXPECTED_SHA256) {
    fs.unlinkSync(tmpTarball);
    throw new Error(
      `SHA256 mismatch on downloaded tarball.\n` +
      `  expected: ${EXPECTED_SHA256}\n` +
      `  actual:   ${actual}\n` +
      'Do NOT use this binary. The download may be corrupt or tampered with.'
    );
  }
  console.log('SHA256 verified.');

  // 5. Extract mongod binary
  console.log('Extracting mongod...');
  await extract(tmpTarball, binDir);

  // 6. Set executable bit
  fs.chmodSync(BINARY_PATH, 0o755);

  // 7. Clean up temp tarball
  fs.unlinkSync(tmpTarball);

  console.log(`mongod binary installed at: ${BINARY_PATH}`);
}

main().catch(err => {
  console.error('download-mongod failed:', err.message);
  process.exit(1);
});
