// download-mongo-binaries.js
// Downloads mongod and mongodump binaries to ~/.nlm/bin/.
// Run via: node scripts/download-mongo-binaries.js
// Idempotent: each binary is checked independently; only missing ones are downloaded.
//
// Lives in front_end/ because it's invoked via npm `predev` to guarantee the
// binary exists before Electron's mongod-manager.ts spawns it. The Python
// backend is a consumer of a running mongod, not the orchestrator — when
// running back_end standalone, the developer starts mongod manually.

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
    // SHA256 from: sha256sum mongodb-database-tools-ubuntu2204-x86_64-100.14.0.tgz
    // No .sha256 sidecar is published for Database Tools — the .tgz.sig (GPG) is
    // the authoritative dev-time trust anchor.
    sha256: '4104998bda784a0cb16fc2e06d9c21645516d72c4fb481c9b103f1e0a8458fc0',
    // Documented at https://www.mongodb.com/docs/database-tools/verify/linux/
    gpg: {
      keyUrl: 'https://pgp.mongodb.com/server-Tools.asc',
      sigUrl: 'https://fastdl.mongodb.org/tools/db/mongodb-database-tools-ubuntu2204-x86_64-100.14.0.tgz.sig',
      keyFingerprint: 'D4E45C292A5C94962F0D10E13132835C1D925D5B',
    },
    tmpTarball: path.join(binDir, 'mongodump.tgz.tmp'),
    label: 'MongoDB Database Tools 100.14.0',
  },
];

// Windows trust anchor is the source-pinned SHA256 below — there is NO
// Authenticode signature check. This is a deliberate, empirically-grounded
// decision, not an omission:
//
//   MongoDB Authenticode-signs only the .msi installers, not the .exe files
//   distributed inside the .zip archives we download. Verified on Windows
//   2026-05-31: Get-AuthenticodeSignature on the extracted mongod.exe (8.0.19)
//   and mongodump.exe (100.14.0) both report Status=NotSigned / SignatureType=
//   None — i.e. no embedded signature bytes at all. MongoDB's own docs
//   (https://www.mongodb.com/docs/database-tools/verify/windows/) only describe
//   verifying .msi packages, which corroborates this.
//
// The SHA256 is pinned in this (version-controlled) source, so it already
// defeats CDN compromise, MitM, and corrupt mirrors — any byte deviation from
// what we pinned. Adding signature parity with Linux mongodump / macOS will
// require switching to .msi downloads + msiexec administrative extraction 
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

const DARWIN_BINARIES = [
  {
    binaryName: 'mongod',
    binaryPath: path.join(binDir, 'mongod'),
    url: 'https://fastdl.mongodb.org/osx/mongodb-macos-arm64-8.0.19.tgz',
    // SHA256 from: curl https://fastdl.mongodb.org/osx/mongodb-macos-arm64-8.0.19.tgz.sha256
    sha256: 'a8a158226d3f2f9fb0618f19473b8a45cd993b12df79f6a1957e450406898b2b',
    tmpTarball: path.join(binDir, 'mongod.tgz.tmp'),
    label: 'MongoDB 8.0.19 (macOS arm64)',
  },
  {
    binaryName: 'mongodump',
    binaryPath: path.join(binDir, 'mongodump'),
    url: 'https://fastdl.mongodb.org/tools/db/mongodb-database-tools-macos-arm64-100.14.0.zip',
    // SHA256 from: shasum -a 256 mongodump.zip (no CDN sidecar)
    sha256: '69ee5a9cc8afd6373ca0723d2c62c7a272c9e629803a361e2f63e61fd32df65e',
    tmpTarball: path.join(binDir, 'mongodump.tmp.zip'),
    label: 'MongoDB Database Tools 100.14.0 (macOS arm64)',
  },
];

// MongoDB's Apple Developer Team ID, per
// https://www.mongodb.com/docs/database-tools/verify/macos/
// Expected codesign Authority chain:
//   Developer ID Application: MongoDB, Inc. (4XWMY46275)
//   Developer ID Certification Authority
//   Apple Root CA
const DARWIN_SIGNING_TEAM_ID = '4XWMY46275';
const DARWIN_SIGNING_IDENTITY = 'MongoDB, Inc.';

function getBinaries(platform = process.platform) {
  switch (platform) {
    case 'win32': return WINDOWS_BINARIES;
    case 'linux': return LINUX_BINARIES;
    case 'darwin': return DARWIN_BINARIES;
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

/** Extract a single binary from a .tgz using system tar (Linux and macOS). */
function extractTgz(archive, destDir, binaryName) {
  // PATH-hardened on darwin: /usr/bin/tar is bsdtar (OS-managed, cannot be
  // PATH-overridden). Plain `tar` on a Mac with Homebrew gnu-tar in PATH
  // resolves to GNU tar, which treats */bin/${binaryName} as a literal path
  // without --wildcards → zero files extracted → ENOENT on chmodSync.
  // bsdtar treats glob characters as wildcards by default; --wildcards is
  // a GNU-only flag (verified unsupported on bsdtar).
  const tarBin = process.platform === 'darwin' ? '/usr/bin/tar' : 'tar';
  const matchFlag = process.platform === 'linux' ? ['--wildcards'] : [];
  return new Promise((resolve, reject) => {
    execFile(
      tarBin,
      ['--strip-components=2', '-xzf', archive, '-C', destDir, ...matchFlag, `*/bin/${binaryName}`],
      (err, _stdout, stderr) => {
        if (err) {
          if (err.code === 'ENOENT') {
            reject(new Error('tar not found — required for extraction (install GNU or BSD tar)'));
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

/** Extract a single binary from a .zip using macOS-preinstalled unzip (darwin). */
function extractZipUnix(archive, destDir, binaryName) {
  return new Promise((resolve, reject) => {
    // PATH-hardened: /usr/bin/unzip is Apple's bundled Info-ZIP. Avoids
    // Homebrew's /opt/homebrew/bin/unzip taking precedence via PATH override.
    execFile('/usr/bin/unzip', ['-j', '-o', archive, `*/bin/${binaryName}`, '-d', destDir],
      (err, _stdout, stderr) => {
        if (err) {
          if (err.code === 'ENOENT') reject(new Error('/usr/bin/unzip not found — required for extraction on macOS'));
          // Exit code 11 from unzip = "no matching files" (verified live).
          else reject(new Error(`unzip failed: ${stderr || err.message}`));
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
 * Verify a darwin binary's code signature against the pinned MongoDB Team ID.
 * Test seam: `_execFileP` defaults to the module-scope `execFileP` for all
 * production callers (two-arg). Tests inject a mock as the third argument.
 */
async function verifyCodesignDarwin(binaryPath, binaryName, _execFileP = execFileP) {
  // 1. Verify the Mach-O signature is intact (non-zero exit on tampering).
  try {
    await _execFileP('/usr/bin/codesign', ['--verify', '--strict', binaryPath]);
  } catch (err) {
    fs.unlinkSync(binaryPath);
    throw new Error(
      `codesign --verify failed for ${binaryName}: ${err.stderr || err.message}\n` +
      'The binary has been deleted. Re-run this script to re-download.'
    );
  }

  // 2. Confirm the signing identity is MongoDB, Inc. (Team ID 4XWMY46275).
  //    codesign writes its info to stderr by convention. Step 1 already proved
  //    the signature is valid; if step 2 throws, treat it as anomalous and
  //    hard-fail WITHOUT consulting any partial output.
  let info;
  try {
    const result = await _execFileP('/usr/bin/codesign', ['-dv', '--verbose=4', binaryPath]);
    info = (result.stderr || '') + (result.stdout || '');
  } catch (err) {
    fs.unlinkSync(binaryPath);
    throw new Error(
      `codesign -dv failed for ${binaryName} after --verify succeeded: ${err.message}\n` +
      'The binary has been deleted. Re-run this script to re-download.'
    );
  }
  if (!info.includes(DARWIN_SIGNING_IDENTITY) || !info.includes(DARWIN_SIGNING_TEAM_ID)) {
    fs.unlinkSync(binaryPath);
    throw new Error(
      `Code signature identity mismatch for ${binaryName}.\n` +
      `  Expected: ${DARWIN_SIGNING_IDENTITY} (${DARWIN_SIGNING_TEAM_ID})\n` +
      `  codesign output:\n${info}\n` +
      'The binary has been deleted. Do NOT use this binary.'
    );
  }
}

function safeUnlink(p) {
  try { fs.unlinkSync(p); } catch (_) { /* outer finally retries via rmSync */ }
}

async function safeRm(p) {
  try { await fs.promises.rm(p, { recursive: true, force: true }); }
  catch (_) { /* leftover tmp dir is non-security; OS tmp reaper handles it */ }
}

/**
 * Verify a Linux tarball's GPG signature against a pinned primary-key fingerprint.
 * Test seams: _execFileP and _download default to module-scope production deps;
 * tests inject mocks via the trailing args.
 */
async function verifyGpgLinux(tarballPath, sigUrl, keyUrl, pinnedFingerprint,
                              _execFileP = execFileP, _download = download) {
  // UP1 / UP1b — gpg presence
  let gpgVersion;
  try {
    const { stdout } = await _execFileP('gpg', ['--version']);
    gpgVersion = stdout.split('\n')[0];
  } catch (err) {
    if (err.code === 'ENOENT') {
      throw new Error(
        'GPG is required for MongoDB Database Tools signature verification on Linux,\n' +
        'but `gpg` was not found on PATH.\n\n' +
        'Install it with one of:\n' +
        '  sudo apt install gnupg            # Debian / Ubuntu\n' +
        '  sudo dnf install gnupg2           # Fedora / RHEL\n' +
        '  sudo pacman -S gnupg              # Arch\n\n' +
        'Then re-run this script.'
      );
    }
    throw new Error(
      'gpg is on PATH but \'gpg --version\' failed unexpectedly.\n' +
      `Underlying error: ${err.message}\n` +
      `stderr: ${err.stderr || '(none)'}\n\n` +
      'This typically indicates a broken gpg installation. Try reinstalling\n' +
      'gnupg or report the issue with the error above.'
    );
  }

  // UP8 — ephemeral keyring directory
  const tmpHome = await fs.promises.mkdtemp(
    path.join(os.tmpdir(), 'mongo-tools-gpg-'));

  try {
    // UP2 — key download
    const keyPath = path.join(tmpHome, 'signing-key.asc');
    try {
      await _download(keyUrl, keyPath, 'GPG signing key');
    } catch (err) {
      throw new Error(
        `Failed to download MongoDB Database Tools signing key from\n  ${keyUrl}\n` +
        `Underlying error: ${err.message}\n` +
        'Check network connectivity and re-run.'
      );
    }

    // UP7 — key import
    try {
      await _execFileP('gpg', ['--homedir', tmpHome, '--import', keyPath]);
    } catch (err) {
      throw new Error(
        `gpg --import failed for the MongoDB Database Tools signing key.\n` +
        `gpg version: ${gpgVersion}\n` +
        `Underlying error: ${err.message}\n` +
        `stderr: ${err.stderr || '(none)'}\n\n` +
        'This may indicate that gpg is too old to parse the key format.\n' +
        'Try upgrading gnupg.'
      );
    }

    // UP4 — sig download
    const sigPath = path.join(tmpHome, 'tarball.tgz.sig');
    try {
      await _download(sigUrl, sigPath, 'GPG signature');
    } catch (err) {
      throw new Error(
        `Failed to download GPG signature from\n  ${sigUrl}\n` +
        `Underlying error: ${err.message}\n` +
        'Check network connectivity and re-run.'
      );
    }

    // UP5 — verify signature
    let verifyStdout;
    try {
      const result = await _execFileP('gpg', [
        '--homedir', tmpHome,
        '--status-fd', '1',
        '--verify', sigPath, tarballPath,
      ]);
      verifyStdout = result.stdout;
    } catch (err) {
      safeUnlink(tarballPath);
      throw new Error(
        'GPG signature verification FAILED for the Database Tools tarball.\n' +
        `  Signature file: ${sigUrl}\n` +
        `  Tarball:        ${tarballPath}\n\n` +
        `gpg exit code: ${err.code}\n` +
        `gpg stderr:\n${err.stderr || '(none)'}\n\n` +
        'This is a serious finding — the downloaded tarball does not have a valid\n' +
        'signature from the pinned MongoDB key. The tarball has been deleted.\n' +
        'Re-run this script to re-download; if the failure persists, investigate\n' +
        'the network path and CDN before installing.'
      );
    }

    // UP3 — VALIDSIG primary-fingerprint check (field 10)
    const match = verifyStdout.match(
      /^\[GNUPG:\] VALIDSIG\s+\S+(?:\s+\S+){8}\s+([0-9A-F]{40})/m);
    if (!match) {
      safeUnlink(tarballPath);
      throw new Error(
        'gpg --verify exited 0 but no VALIDSIG status line was found in stdout.\n' +
        'This is unexpected gpg behavior. The tarball has been deleted.\n' +
        `gpg version: ${gpgVersion}\n` +
        `stdout:\n${verifyStdout}`
      );
    }
    const pin = pinnedFingerprint.toUpperCase();
    if (match[1] !== pin) {
      safeUnlink(tarballPath);
      throw new Error(
        'GPG signature was made by a key that is NOT our pinned trust anchor.\n' +
        `  Expected pin:                 ${pin}\n` +
        `  Signed by primary (VALIDSIG): ${match[1]}\n\n` +
        'The tarball\'s SHA256 already matched the source-pinned hash, so the\n' +
        'downloaded bytes are not tampered. This is a trust-anchor mismatch.\n\n' +
        'Possible causes:\n' +
        '  (a) MongoDB rotated their signing key — independently verify the new\n' +
        '      fingerprint via MongoDB\'s documentation, then update the pin in\n' +
        '      front_end/scripts/download-mongo-binaries.js.\n' +
        '  (b) Active MitM at https://pgp.mongodb.com paired with a substituted\n' +
        '      .sig — investigate the network paths to pgp.mongodb.com and\n' +
        '      fastdl.mongodb.org before proceeding.\n\n' +
        'The tarball has been deleted. Refusing to install until trust anchor\n' +
        'is reconciled.'
      );
    }

    console.log('  GPG signature verified.');
  } finally {
    try { await _execFileP('gpgconf', ['--homedir', tmpHome, '--kill', 'all']); }
    catch (_) { /* gpgconf missing or non-zero — agent self-terminates on idle */ }
    await safeRm(tmpHome);
  }
}

/**
 * Dispatch extraction by platform.
 * extractTgz uses system tar (bsdtar on darwin, GNU tar on linux).
 * extractWindows uses PowerShell Expand-Archive + recursive walk.
 * darwin routes by archive type — tmpTarball extension is the contract.
 */
function extract(platform, archive, destDir, binaryName) {
  switch (platform) {
    case 'linux':  return extractTgz(archive, destDir, binaryName);
    case 'win32':  return extractWindows(archive, destDir, binaryName);
    // darwin: route by archive type — tmpTarball extension is the contract.
    // mongod → .tgz.tmp → extractTgz; mongodump → .tmp.zip → extractZipUnix.
    case 'darwin':
      return archive.endsWith('.zip')
        ? extractZipUnix(archive, destDir, binaryName)
        : extractTgz(archive, destDir, binaryName);
    default:
      throw new Error(`Unsupported platform for extraction: ${platform}`);
  }
}

/** Download, verify, extract, chmod, and clean up one binary. */
async function installBinary({ binaryName, binaryPath, url, sha256, tmpTarball, label, gpg }) {
  if (!sha256 || sha256.length !== 64) {
    throw new Error(`SHA256 not configured for ${binaryName}. Fill in the SHA256 for this platform's binary table before shipping.`);
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

  // GPG verify (linux tools only) + extract — always clean up the archive
  console.log(`  Extracting ${binaryName}...`);
  try {
    if (process.platform === 'linux' && gpg) {
      await verifyGpgLinux(tmpTarball, gpg.sigUrl, gpg.keyUrl, gpg.keyFingerprint);
    }
    await extract(process.platform, tmpTarball, binDir, binaryName);
  } finally {
    fs.rmSync(tmpTarball, { force: true });
  }

  // Verify codesign before chmod — on failure, deletes the non-executable binary.
  if (process.platform === 'darwin') {
    await verifyCodesignDarwin(binaryPath, binaryName);
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

module.exports = { getBinaries, main, verifyCodesignDarwin, verifyGpgLinux };
