// mongod-manager.test.ts
// Unit tests for mongod-manager.ts lifecycle management.
//
// Key Vitest constraints:
//   - vi.mock() factory results are CACHED — same vi.fn() instances reused across
//     vi.resetModules() cycles. vi.clearAllMocks() is required in beforeEach to
//     reset accumulated call counts.
//   - process.nextTick is NOT mocked by vi.useFakeTimers() (excluded from default
//     toFake list in Vitest 3.2.4).
//   - Socket mocks must include destroy: vi.fn() — portOpen() calls socket.destroy()
//     in both handlers. Without it, the handler throws and portOpen never resolves.
//   - Proc event emission (error/exit) must be scheduled INSIDE the spawn mock
//     implementation, not from the test body. This guarantees it fires AFTER
//     proc.on('error') and proc.on('exit') are registered in _doStart().

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { EventEmitter } from 'events';

// ─── Hoisted mocks ────────────────────────────────────────────────────────────

vi.mock('electron', () => ({
  app: {
    isPackaged: false,
    getPath: vi.fn().mockReturnValue('/tmp/test-userData'),
  },
}));

vi.mock('child_process', () => ({ spawn: vi.fn() }));
vi.mock('net',          () => ({ createConnection: vi.fn() }));
vi.mock('fs',           () => ({
  mkdirSync:  vi.fn(),
  unlinkSync: vi.fn(),
  existsSync: vi.fn(),
}));

// ─── Test state ───────────────────────────────────────────────────────────────

let ensureMongodRunning: typeof import('../src/main/mongod-manager').ensureMongodRunning;
let stopMongod:          typeof import('../src/main/mongod-manager').stopMongod;
let mockSpawn:           ReturnType<typeof vi.fn>;
let mockNet:             { createConnection: ReturnType<typeof vi.fn> };
let mockFs:              {
  mkdirSync:  ReturnType<typeof vi.fn>;
  unlinkSync: ReturnType<typeof vi.fn>;
  existsSync: ReturnType<typeof vi.fn>;
};

beforeEach(async () => {
  // Reset module registry → fresh mongodProcess and startPromise on re-import.
  vi.resetModules();

  const mod    = await import('../src/main/mongod-manager');
  const cpMod  = await import('child_process');
  const netMod = await import('net');
  const fsMod  = await import('fs');

  ensureMongodRunning = mod.ensureMongodRunning;
  stopMongod          = mod.stopMongod;

  mockSpawn = vi.mocked(cpMod.spawn);
  mockNet   = { createConnection: vi.mocked((netMod as any).createConnection) };
  mockFs    = {
    mkdirSync:  vi.mocked((fsMod as any).mkdirSync),
    unlinkSync: vi.mocked((fsMod as any).unlinkSync),
    existsSync: vi.mocked((fsMod as any).existsSync),
  };

  // vi.mock() factory results are cached — same vi.fn() instances survive
  // vi.resetModules(). Clear accumulated call counts before each test.
  vi.clearAllMocks();

  vi.spyOn(console, 'log').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** ChildProcess-like EventEmitter with stdout, stderr, kill. */
function makeProc(pid = 12345) {
  const proc = new EventEmitter() as any;
  proc.pid    = pid;
  proc.stdout = new EventEmitter();
  proc.stderr = new EventEmitter();
  proc.kill   = vi.fn();
  return proc;
}

/**
 * Socket-like EventEmitter with destroy().
 * portOpen() calls socket.destroy() in both 'connect' and 'error' handlers.
 * A plain EventEmitter lacks destroy() — the handler throws and portOpen hangs.
 */
function makeSocket() {
  const s = new EventEmitter() as any;
  s.destroy = vi.fn();
  return s;
}

/** net.createConnection always emits 'connect' (port open). */
function netAccepts() {
  mockNet.createConnection.mockImplementation(() => {
    const s = makeSocket();
    process.nextTick(() => s.emit('connect'));
    return s;
  });
}

/** net.createConnection always emits 'error' (port closed). */
function netRefuses() {
  mockNet.createConnection.mockImplementation(() => {
    const s = makeSocket();
    process.nextTick(() => s.emit('error', new Error('ECONNREFUSED')));
    return s;
  });
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('Mongod Manager', () => {

  // 1. Pre-check: port already open → fast-path, no spawn
  it('returns true immediately when port is already open (existing mongod)', async () => {
    netAccepts();
    const result = await ensureMongodRunning();
    expect(result).toBe(true);
    expect(mockSpawn).not.toHaveBeenCalled();
  });

  // 2. Happy path: spawn succeeds, port opens on first poll
  it('returns true when mongod spawns and port opens', async () => {
    let call = 0;
    mockNet.createConnection.mockImplementation(() => {
      const s = makeSocket();
      call++;
      if (call === 1) process.nextTick(() => s.emit('error', new Error('ECONNREFUSED')));
      else            process.nextTick(() => s.emit('connect'));
      return s;
    });

    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);

    const result = await ensureMongodRunning();
    expect(result).toBe(true);
    expect(mockSpawn).toHaveBeenCalledOnce();
  });

  // 3. Binary not found: spawn emits ENOENT → returns false.
  //    proc events are scheduled INSIDE the spawn mock so they fire after
  //    proc.on('error') and proc.on('exit') are registered in _doStart().
  it('returns false and logs ENOENT when binary is not found', async () => {
    netRefuses();

    mockSpawn.mockImplementation(() => {
      const proc = makeProc();
      process.nextTick(() => {
        const err = Object.assign(new Error('spawn ENOENT'), { code: 'ENOENT' }) as NodeJS.ErrnoException;
        proc.emit('error', err);
        proc.emit('exit', 1);
      });
      return proc;
    });

    const result = await ensureMongodRunning();

    expect(result).toBe(false);
    expect(console.error).toHaveBeenCalledWith(expect.stringContaining('ENOENT'));
  });

  // 4. Port never opens → pollConnect exhausts → returns false.
  //    Fake timers required: real sleep(1000) × 30 = 30s > testTimeout.
  it('returns false when port never opens (timeout)', async () => {
    vi.useFakeTimers();
    netRefuses();

    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);
    // proc never emits 'exit' — exitSignal never resolves

    const resultPromise = ensureMongodRunning();
    await vi.advanceTimersByTimeAsync(30_000);

    expect(await resultPromise).toBe(false);
    vi.useRealTimers();
  });

  // 5. mongod exits immediately → exitSignal wins the race, returns false fast.
  //    Fake timers prove no real time advanced (sleep timers still pending).
  it('returns false fast when mongod exits immediately (exitSignal wins)', async () => {
    vi.useFakeTimers();
    netRefuses();

    mockSpawn.mockImplementation(() => {
      const proc = makeProc();
      process.nextTick(() => proc.emit('exit', 1));
      return proc;
    });

    const result = await ensureMongodRunning();

    expect(result).toBe(false);
    expect(vi.getTimerCount()).toBeGreaterThan(0); // sleep timers still pending
    vi.useRealTimers();
  });

  // 6. WiredTiger.lock handling:
  //    Case A — port free → unlinkSync called (lock is stale)
  //    Case B — mongodProcess already set → fast-path, unlinkSync not called again
  it('deletes WiredTiger.lock when pre-check fails; not on subsequent fast-path call', async () => {
    // Case A: pre-check fails → port free → spawn → lock deleted
    let call = 0;
    mockNet.createConnection.mockImplementation(() => {
      const s = makeSocket();
      call++;
      if (call === 1) process.nextTick(() => s.emit('error', new Error('ECONNREFUSED')));
      else            process.nextTick(() => s.emit('connect'));
      return s;
    });

    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);

    await ensureMongodRunning();
    expect(mockFs.unlinkSync).toHaveBeenCalled();

    // Case B: mongodProcess is now set → fast-path via `if (mongodProcess)` →
    // portOpen never called, unlinkSync never called again.
    const unlinkCountAfterA = mockFs.unlinkSync.mock.calls.length;
    await ensureMongodRunning();
    expect(mockFs.unlinkSync.mock.calls.length).toBe(unlinkCountAfterA);
    expect(mockSpawn).toHaveBeenCalledOnce(); // still only one spawn
  });

  // 7. stopMongod: sends SIGTERM when managed; no-op otherwise
  it('sends SIGTERM when mongod is managed by us; is a no-op otherwise', async () => {
    // No-op when nothing spawned
    stopMongod();
    expect(mockSpawn).not.toHaveBeenCalled();

    // Start mongod
    let call = 0;
    mockNet.createConnection.mockImplementation(() => {
      const s = makeSocket();
      call++;
      if (call === 1) process.nextTick(() => s.emit('error', new Error('ECONNREFUSED')));
      else            process.nextTick(() => s.emit('connect'));
      return s;
    });

    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);
    await ensureMongodRunning();

    // Stop on Linux → SIGTERM
    const orig = process.platform;
    Object.defineProperty(process, 'platform', { value: 'linux', configurable: true });
    stopMongod();
    expect(proc.kill).toHaveBeenCalledWith('SIGTERM');
    Object.defineProperty(process, 'platform', { value: orig, configurable: true });

    // Second stop → no-op (mongodProcess is null)
    proc.kill.mockClear();
    stopMongod();
    expect(proc.kill).not.toHaveBeenCalled();
  });

  // 8. stopMongod: sends SIGTERM on darwin (same as linux — not taskkill)
  it('sends SIGTERM on darwin; does not call taskkill', async () => {
    let call = 0;
    mockNet.createConnection.mockImplementation(() => {
      const s = makeSocket();
      call++;
      if (call === 1) process.nextTick(() => s.emit('error', new Error('ECONNREFUSED')));
      else            process.nextTick(() => s.emit('connect'));
      return s;
    });

    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);
    await ensureMongodRunning();

    const orig = process.platform;
    try {
      Object.defineProperty(process, 'platform', { value: 'darwin', configurable: true });
      stopMongod();
      expect(proc.kill).toHaveBeenCalledWith('SIGTERM');
      const taskkillCalls = mockSpawn.mock.calls.filter(c => c[0] === 'taskkill');
      expect(taskkillCalls).toHaveLength(0);
    } finally {
      Object.defineProperty(process, 'platform', { value: orig, configurable: true });
    }
  });

  // 9. Concurrency guard: two simultaneous calls → one spawn, both get true
  it('two concurrent ensureMongodRunning() calls share the same Promise (one spawn)', async () => {
    let call = 0;
    mockNet.createConnection.mockImplementation(() => {
      const s = makeSocket();
      call++;
      if (call === 1) process.nextTick(() => s.emit('error', new Error('ECONNREFUSED')));
      else            process.nextTick(() => s.emit('connect'));
      return s;
    });

    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);

    const [r1, r2] = await Promise.all([ensureMongodRunning(), ensureMongodRunning()]);

    expect(r1).toBe(true);
    expect(r2).toBe(true);
    expect(mockSpawn).toHaveBeenCalledOnce();
  });

});
