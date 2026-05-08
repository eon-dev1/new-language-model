// Tests for getBinaries() platform dispatch and main() idempotency.
// All tests pass platform explicitly — CI-safe on any OS.

'use strict';

const { getBinaries, main } = require('../scripts/download-mongo-binaries.js');
const fs = require('fs');

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

  it('darwin — throws macOS not implemented', () => {
    expect(() => getBinaries('darwin')).toThrow(/macOS support not yet implemented/);
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
