// Tests for getBinaries() platform dispatch, main() idempotency,
// and verifyCodesignDarwin() security check.
// All tests pass platform explicitly — CI-safe on any OS.

'use strict';

const { getBinaries, main, verifyCodesignDarwin, verifyGpgLinux } = require('../scripts/download-mongo-binaries.js');
const fs = require('fs');
const os = require('os');
const path = require('path');

describe('getBinaries()', () => {
  it('win32 — returns .exe paths and Windows zip URLs', () => {
    const bins = getBinaries('win32');
    expect(bins).toHaveLength(2);

    const mongod = bins.find(b => b.binaryName === 'mongod.exe');
    expect(mongod).toBeDefined();
    expect(mongod.binaryPath).toMatch(/mongod\.exe$/);
    expect(mongod.url).toMatch(/windows/);
    expect(mongod.url).toMatch(/\.zip$/);
    expect(mongod.tmpTarball).toMatch(/\.tmp\.zip$/);

    const mongodump = bins.find(b => b.binaryName === 'mongodump.exe');
    expect(mongodump).toBeDefined();
    expect(mongodump.binaryPath).toMatch(/mongodump\.exe$/);
    expect(mongodump.url).toMatch(/\.zip$/);
  });

  it('linux — returns no-extension paths and ubuntu tgz URLs', () => {
    const bins = getBinaries('linux');
    expect(bins).toHaveLength(2);

    const mongod = bins.find(b => b.binaryName === 'mongod');
    expect(mongod).toBeDefined();
    expect(mongod.binaryPath).not.toMatch(/\.exe$/);
    expect(mongod.url).toMatch(/ubuntu/);
    expect(mongod.url).toMatch(/\.tgz$/);
    expect(mongod.tmpTarball).toMatch(/\.tgz\.tmp$/);

    const mongodump = bins.find(b => b.binaryName === 'mongodump');
    expect(mongodump).toBeDefined();
    expect(mongodump.binaryPath).not.toMatch(/\.exe$/);
    expect(mongodump.url).toMatch(/\.tgz$/);
  });

  it('darwin — returns arm64 tgz for mongod and arm64 zip for mongodump', () => {
    const bins = getBinaries('darwin');
    expect(bins).toHaveLength(2);

    const mongod = bins.find(b => b.binaryName === 'mongod');
    expect(mongod).toBeDefined();
    expect(mongod.binaryPath).not.toMatch(/\.exe$/);
    expect(mongod.url).toMatch(/macos|osx/);
    expect(mongod.url).toMatch(/arm64/);
    expect(mongod.url).toMatch(/\.tgz$/);
    expect(mongod.tmpTarball).toMatch(/\.tgz\.tmp$/);

    const mongodump = bins.find(b => b.binaryName === 'mongodump');
    expect(mongodump).toBeDefined();
    expect(mongodump.binaryPath).not.toMatch(/\.exe$/);
    expect(mongodump.url).toMatch(/arm64/);
    expect(mongodump.url).toMatch(/\.zip$/);
    expect(mongodump.tmpTarball).toMatch(/\.tmp\.zip$/);
  });

  it('freebsd — throws unsupported platform', () => {
    expect(() => getBinaries('freebsd')).toThrow(/Unsupported platform/);
  });
});

describe('main() idempotency', () => {
  it('skips download when all binaryPaths already exist', async () => {
    const existsSpy = vi.spyOn(fs, 'existsSync').mockReturnValue(true);
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    try {
      await main();
      expect(logSpy).toHaveBeenCalledWith('mongod and mongodump already present — skipping download.');
    } finally {
      existsSpy.mockRestore();
      logSpy.mockRestore();
    }
  });
});

describe('verifyCodesignDarwin()', () => {
  // Mock is injected via the test-seam third parameter (_execFileP = execFileP).
  // The mock is async+throws — matching the execFileP promisified surface,
  // not (cmd, args, cb) which is the raw execFile callback shape.
  function makeExecMock({ verifyFails, dvFails, dvStderr } = {}) {
    return vi.fn().mockImplementation(async (cmd, args) => {
      if (args.includes('--verify')) {
        if (verifyFails) throw Object.assign(new Error('invalid signature'), { stderr: 'invalid signature' });
        return { stdout: '', stderr: '' };
      }
      if (dvFails) throw new Error('codesign -dv error');
      return { stdout: '', stderr: dvStderr ?? 'Developer ID Application: MongoDB, Inc. (4XWMY46275)' };
    });
  }

  it('1. happy path — resolves without throw, unlinkSync not called', async () => {
    const exec = makeExecMock();
    const unlinkSpy = vi.spyOn(fs, 'unlinkSync').mockImplementation(() => {});
    try {
      await expect(verifyCodesignDarwin('/fake/mongod', 'mongod', exec)).resolves.toBeUndefined();
      expect(unlinkSpy).not.toHaveBeenCalled();
    } finally {
      unlinkSpy.mockRestore();
    }
  });

  it('2. identity mismatch — rejects with /identity mismatch/, unlinkSync called', async () => {
    const exec = makeExecMock({ dvStderr: 'Developer ID Application: Some Other, Inc. (XXXXXXXXXX)' });
    const unlinkSpy = vi.spyOn(fs, 'unlinkSync').mockImplementation(() => {});
    try {
      await expect(verifyCodesignDarwin('/fake/mongod', 'mongod', exec)).rejects.toThrow(/identity mismatch/);
      expect(unlinkSpy).toHaveBeenCalledWith('/fake/mongod');
    } finally {
      unlinkSpy.mockRestore();
    }
  });

  it('3. --verify fails — rejects with /codesign --verify failed/, unlinkSync called, -dv not reached', async () => {
    const exec = makeExecMock({ verifyFails: true });
    const unlinkSpy = vi.spyOn(fs, 'unlinkSync').mockImplementation(() => {});
    try {
      await expect(verifyCodesignDarwin('/fake/mongod', 'mongod', exec)).rejects.toThrow(/codesign --verify failed/);
      expect(unlinkSpy).toHaveBeenCalledWith('/fake/mongod');
      const dvCalls = exec.mock.calls.filter(c => c[1].includes('-dv'));
      expect(dvCalls).toHaveLength(0);
    } finally {
      unlinkSpy.mockRestore();
    }
  });

  it('4. -dv fails after --verify succeeded — rejects with /codesign -dv failed/, unlinkSync called', async () => {
    const exec = makeExecMock({ dvFails: true });
    const unlinkSpy = vi.spyOn(fs, 'unlinkSync').mockImplementation(() => {});
    try {
      await expect(verifyCodesignDarwin('/fake/mongod', 'mongod', exec)).rejects.toThrow(/codesign -dv failed/);
      expect(unlinkSpy).toHaveBeenCalledWith('/fake/mongod');
    } finally {
      unlinkSpy.mockRestore();
    }
  });
});

// ─── verifyGpgLinux ──────────────────────────────────────────────────────────

describe('verifyGpgLinux()', () => {
  const PINNED_FPR = 'D4E45C292A5C94962F0D10E13132835C1D925D5B';
  const ATTACKER_FPR = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA';
  const SUBKEY_FPR = 'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB';

  function validsigLine(primaryFpr, signingFpr = primaryFpr) {
    return `[GNUPG:] VALIDSIG ${signingFpr} 2024-01-15 1705344000 0 4 0 1 10 01 ${primaryFpr}`;
  }

  function makeExecMock(overrides = {}) {
    return vi.fn().mockImplementation(async (cmd, args) => {
      if (cmd === 'gpgconf') return { stdout: '', stderr: '' };
      if (args.includes('--version')) {
        if (overrides.versionThrows) throw overrides.versionThrows;
        return { stdout: 'gpg (GnuPG) 2.2.27\n', stderr: '' };
      }
      if (args.includes('--import')) {
        if (overrides.importThrows) throw overrides.importThrows;
        return { stdout: '', stderr: '' };
      }
      if (args.includes('--verify')) {
        if (overrides.verifyThrows) throw overrides.verifyThrows;
        return {
          stdout: overrides.verifyStdout ?? validsigLine(PINNED_FPR),
          stderr: 'gpg: WARNING: This key is not certified with a trusted signature!\n',
        };
      }
      return { stdout: '', stderr: '' };
    });
  }

  function makeDownloadMock(overrides = {}) {
    return vi.fn().mockImplementation(async (url, dest, _label) => {
      if (url.endsWith('.asc') && overrides.keyThrows) throw overrides.keyThrows;
      if (url.endsWith('.sig') && overrides.sigThrows) throw overrides.sigThrows;
      fs.writeFileSync(dest, 'mock-data');
    });
  }

  function captureHomedir(execMock) {
    for (const [cmd, args] of execMock.mock.calls) {
      if (cmd !== 'gpg' && cmd !== 'gpgconf') continue;
      const idx = args.indexOf('--homedir');
      if (idx >= 0) return args[idx + 1];
    }
    return null;
  }

  it('happy path — resolves, logs verification, cleans up keyring', async () => {
    const exec = makeExecMock();
    const dl = makeDownloadMock();
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    const tarball = path.join(os.tmpdir(), `gpg-test-tarball-${Date.now()}`);
    fs.writeFileSync(tarball, 'tarball-bytes');
    try {
      await expect(
        verifyGpgLinux(tarball, 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl)
      ).resolves.toBeUndefined();
      expect(logSpy).toHaveBeenCalledWith('  GPG signature verified.');
      expect(fs.existsSync(tarball)).toBe(true);
      const homedir = captureHomedir(exec);
      expect(homedir).toBeTruthy();
      expect(fs.existsSync(homedir)).toBe(false);
    } finally {
      logSpy.mockRestore();
      try { fs.unlinkSync(tarball); } catch (_) {}
    }
  });

  it('UP3 sub-case — signing subkey (field 1 ≠ field 10), field 10 matches pin — passes', async () => {
    const exec = makeExecMock({
      verifyStdout: validsigLine(PINNED_FPR, SUBKEY_FPR),
    });
    const dl = makeDownloadMock();
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    try {
      await expect(
        verifyGpgLinux('/fake/tarball', 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl)
      ).resolves.toBeUndefined();
      expect(logSpy).toHaveBeenCalledWith('  GPG signature verified.');
    } finally {
      logSpy.mockRestore();
    }
  });

  it('UP1 — gpg not on PATH — rejects with install instructions', async () => {
    const exec = makeExecMock({
      versionThrows: Object.assign(new Error('spawn gpg ENOENT'), { code: 'ENOENT' }),
    });
    const dl = makeDownloadMock();
    await expect(
      verifyGpgLinux('/fake/tarball', 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl)
    ).rejects.toThrow(/gpg.*was not found on PATH/);
  });

  it('UP1b — gpg --version fails non-ENOENT — rejects with broken-install message', async () => {
    const exec = makeExecMock({
      versionThrows: Object.assign(new Error('EACCES'), { stderr: 'permission denied' }),
    });
    const dl = makeDownloadMock();
    await expect(
      verifyGpgLinux('/fake/tarball', 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl)
    ).rejects.toThrow(/gpg is on PATH but 'gpg --version' failed/);
  });

  it('UP2 — key download fails — rejects, cleans up keyring', async () => {
    const exec = makeExecMock();
    const dl = makeDownloadMock({ keyThrows: new Error('ECONNREFUSED') });
    try {
      await verifyGpgLinux('/fake/tarball', 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl);
      expect.unreachable('should have thrown');
    } catch (err) {
      expect(err.message).toMatch(/Failed to download.*signing key/);
      const homedir = captureHomedir(exec);
      if (homedir) expect(fs.existsSync(homedir)).toBe(false);
    }
  });

  it('UP3 — wrong signer — rejects with trust-anchor mismatch, tarball deleted', async () => {
    const exec = makeExecMock({
      verifyStdout: validsigLine(ATTACKER_FPR),
    });
    const dl = makeDownloadMock();
    const tarball = path.join(os.tmpdir(), `gpg-test-tarball-up3-${Date.now()}`);
    fs.writeFileSync(tarball, 'tarball-bytes');
    try {
      await verifyGpgLinux(tarball, 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl);
      expect.unreachable('should have thrown');
    } catch (err) {
      expect(err.message).toMatch(/NOT our pinned trust anchor/);
      expect(err.message).toContain(ATTACKER_FPR);
      expect(err.message).toContain(PINNED_FPR);
      expect(fs.existsSync(tarball)).toBe(false);
      const homedir = captureHomedir(exec);
      expect(homedir).toBeTruthy();
      expect(fs.existsSync(homedir)).toBe(false);
    }
  });

  it('UP4 — sig download fails — rejects, cleans up keyring', async () => {
    const exec = makeExecMock();
    const dl = makeDownloadMock({ sigThrows: new Error('HTTP 404') });
    try {
      await verifyGpgLinux('/fake/tarball', 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl);
      expect.unreachable('should have thrown');
    } catch (err) {
      expect(err.message).toMatch(/Failed to download GPG signature/);
      const homedir = captureHomedir(exec);
      if (homedir) expect(fs.existsSync(homedir)).toBe(false);
    }
  });

  it('UP5 — gpg --verify non-zero exit — rejects with BAD signature message, tarball deleted', async () => {
    const verifyErr = new Error('verification failed');
    verifyErr.code = 2;
    verifyErr.stderr = 'gpg: BAD signature from "MongoDB Database Tools"';
    const exec = makeExecMock({ verifyThrows: verifyErr });
    const dl = makeDownloadMock();
    const tarball = path.join(os.tmpdir(), `gpg-test-tarball-up5-${Date.now()}`);
    fs.writeFileSync(tarball, 'tarball-bytes');
    try {
      await verifyGpgLinux(tarball, 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl);
      expect.unreachable('should have thrown');
    } catch (err) {
      expect(err.message).toMatch(/GPG signature verification FAILED/);
      expect(err.message).toContain('BAD signature');
      expect(fs.existsSync(tarball)).toBe(false);
      const homedir = captureHomedir(exec);
      expect(homedir).toBeTruthy();
      expect(fs.existsSync(homedir)).toBe(false);
    }
  });

  it('UP7 — gpg --import fails — rejects with version info, cleans up keyring', async () => {
    const exec = makeExecMock({
      importThrows: Object.assign(new Error('bad key format'), { stderr: 'unsupported algorithm' }),
    });
    const dl = makeDownloadMock();
    try {
      await verifyGpgLinux('/fake/tarball', 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl);
      expect.unreachable('should have thrown');
    } catch (err) {
      expect(err.message).toMatch(/gpg --import failed/);
      expect(err.message).toContain('2.2.27');
      const homedir = captureHomedir(exec);
      if (homedir) expect(fs.existsSync(homedir)).toBe(false);
    }
  });

  it('no VALIDSIG line — gpg exit 0 but missing status — rejects', async () => {
    const exec = makeExecMock({
      verifyStdout: '[GNUPG:] GOODSIG ABC123 MongoDB\n',
    });
    const dl = makeDownloadMock();
    try {
      await verifyGpgLinux('/fake/tarball', 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl);
      expect.unreachable('should have thrown');
    } catch (err) {
      expect(err.message).toMatch(/no VALIDSIG status line/);
    }
  });

  it('inner-unlink failure during UP3 — safeUnlink swallows, UP3 message survives', async () => {
    const exec = makeExecMock({
      verifyStdout: validsigLine(ATTACKER_FPR),
    });
    const dl = makeDownloadMock();
    const unlinkSpy = vi.spyOn(fs, 'unlinkSync').mockImplementation(() => {
      throw new Error('EBUSY');
    });
    try {
      await verifyGpgLinux('/fake/tarball', 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl);
      expect.unreachable('should have thrown');
    } catch (err) {
      expect(err.message).toMatch(/NOT our pinned trust anchor/);
      expect(err.message).not.toContain('EBUSY');
    } finally {
      unlinkSpy.mockRestore();
    }
  });

  it('inner-unlink failure during UP5 — safeUnlink swallows, UP5 message survives', async () => {
    const verifyErr = new Error('verification failed');
    verifyErr.code = 2;
    verifyErr.stderr = 'BAD signature';
    const exec = makeExecMock({ verifyThrows: verifyErr });
    const dl = makeDownloadMock();
    const unlinkSpy = vi.spyOn(fs, 'unlinkSync').mockImplementation(() => {
      throw new Error('EBUSY');
    });
    try {
      await verifyGpgLinux('/fake/tarball', 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl);
      expect.unreachable('should have thrown');
    } catch (err) {
      expect(err.message).toMatch(/GPG signature verification FAILED/);
      expect(err.message).not.toContain('EBUSY');
    } finally {
      unlinkSpy.mockRestore();
    }
  });

  it('finally-block rm failure during UP3 — safeRm swallows, UP3 message survives', async () => {
    const exec = makeExecMock({
      verifyStdout: validsigLine(ATTACKER_FPR),
    });
    const dl = makeDownloadMock();
    const rmSpy = vi.spyOn(fs.promises, 'rm').mockRejectedValue(new Error('EPERM'));
    let leakedHomedir;
    try {
      await verifyGpgLinux('/fake/tarball', 'https://x.com/t.tgz.sig', 'https://x.com/k.asc', PINNED_FPR, exec, dl);
      expect.unreachable('should have thrown');
    } catch (err) {
      expect(err.message).toMatch(/NOT our pinned trust anchor/);
      expect(err.message).not.toContain('EPERM');
      leakedHomedir = captureHomedir(exec);
    } finally {
      rmSpy.mockRestore();
      if (leakedHomedir) fs.rmSync(leakedHomedir, { recursive: true, force: true });
    }
  });

  it('linux config — mongodump entry has gpg field with expected shape', () => {
    const bins = getBinaries('linux');
    const mongodump = bins.find(b => b.binaryName === 'mongodump');
    expect(mongodump.gpg).toBeDefined();
    expect(mongodump.gpg.keyUrl).toMatch(/pgp\.mongodb\.com/);
    expect(mongodump.gpg.sigUrl).toMatch(/\.tgz\.sig$/);
    expect(mongodump.gpg.keyFingerprint).toMatch(/^[0-9A-F]{40}$/);

    const mongod = bins.find(b => b.binaryName === 'mongod');
    expect(mongod.gpg).toBeUndefined();
  });
});
