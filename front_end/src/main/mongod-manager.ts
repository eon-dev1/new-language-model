// mongod-manager.ts
// Manages the bundled mongod binary lifecycle from Electron's main process.
// Modeled on backend-manager.ts.

import { spawn, ChildProcess } from 'child_process';
import * as net from 'net';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { app } from 'electron';

const MONGOD_PORT    = 27019;
const MAX_RETRIES    = 30;
const RETRY_INTERVAL = 1000;  // ms

// Dev path only. __dirname = dist/main/ at runtime (webpack: node.__dirname: false).
const binPath = path.join(os.homedir(), '.nlm', 'bin', 'mongod');

// Module-level state — reset between tests via vi.resetModules() + dynamic import.
let mongodProcess: ChildProcess | null = null;

/**
 * Concurrency guard: concurrent callers await the same in-flight Promise.
 * Resets automatically via .finally() after the attempt completes.
 *
 * Note: if mongodProcess is set to null by a post-startup crash, a subsequent
 * call to ensureMongodRunning() will re-enter _doStart() and attempt to respawn.
 * Since main.ts calls ensureMongodRunning() only once at startup, this is moot
 * today but documented for future callers.
 */
let startPromise: Promise<boolean> | null = null;

// ─── Internal helpers ─────────────────────────────────────────────────────────

/**
 * Returns true for lines that should reach the Electron logger.
 * Suppresses severity "I" (Informational) to eliminate WiredTiger startup
 * churn and routine connection messages. W/E/F always pass through.
 * Non-JSON lines (plain text) always pass through unchanged.
 */
function shouldLogMongodLine(line: string): boolean {
  try {
    const parsed = JSON.parse(line);
    const severity = parsed?.s;
    return severity === 'W' || severity === 'E' || severity === 'F';
  } catch {
    return true; // non-JSON lines always pass through
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Attempt a TCP connection to 127.0.0.1:port.
 * Resolves true on connect, false on error.
 * socket.destroy() is called in both handlers to prevent leaked connections.
 */
function portOpen(port: number): Promise<boolean> {
  return new Promise(resolve => {
    const socket = net.createConnection(port, '127.0.0.1');
    socket.on('connect', () => { socket.destroy(); resolve(true);  });
    socket.on('error',   () => { socket.destroy(); resolve(false); });
  });
}

/**
 * Poll portOpen() until it returns true or MAX_RETRIES is exhausted.
 * Plain async function — NOT new Promise(async executor), which silently
 * swallows errors thrown inside the executor.
 */
async function pollConnect(): Promise<boolean> {
  for (let i = 0; i < MAX_RETRIES; i++) {
    if (await portOpen(MONGOD_PORT)) return true;
    await sleep(RETRY_INTERVAL);
  }
  return false;
}

/**
 * Resolves false as soon as proc emits 'exit'.
 * Typed as Promise<false> so Promise.race([pollConnect(), exitSignal(proc)])
 * returns Promise<boolean> without a cast.
 */
function exitSignal(proc: ChildProcess): Promise<false> {
  return new Promise(resolve => proc.on('exit', () => resolve(false)));
}

/**
 * Core startup logic. Must never reject — main.ts uses `if (!(await ensureMongodRunning()))`.
 * An unhandled rejection here would bypass that check.
 *
 * Uses ~/.nlm/db/ as the data directory (shared with pytest test runner).
 * No dependency on app.whenReady() — os.homedir() works at any time.
 */
async function _doStart(): Promise<boolean> {
  try {
    const dbPath = path.join(os.homedir(), '.nlm', 'db');

    // 1. Create data directory
    fs.mkdirSync(dbPath, { recursive: true });

    // 2. TCP pre-check: if port is already accepting connections, a mongod is
    //    already running. Fast-path return — do NOT touch WiredTiger.lock.
    //    (Deleting the lock of a running mongod would allow a second instance
    //    to acquire a new flock() on a fresh inode — data corruption risk.)
    if (await portOpen(MONGOD_PORT)) {
      console.log('[Mongod Manager] Port already accepting connections — assuming existing mongod, skipping spawn.');
      return true;
    }

    // 3. Port confirmed free → any WiredTiger.lock is definitionally stale.
    try {
      fs.unlinkSync(path.join(dbPath, 'WiredTiger.lock'));
    } catch {
      // Expected if file doesn't exist — not an error.
    }

    // 4. Spawn mongod
    // --noauth was removed in MongoDB 6+. Auth is off by default without --auth.
    console.log('[Mongod Manager] Spawning mongod...');
    const proc = spawn(binPath, [
      '--port',     String(MONGOD_PORT),
      '--dbpath',   dbPath,
      '--bind_ip',  '127.0.0.1',
    ], {
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
      // Disable glibc rseq to avoid tcmalloc-google incompatibility warning.
      // Without this, MongoDB logs: "glibc rseq support active — critical performance implications".
      env: { ...process.env, GLIBC_TUNABLES: 'glibc.pthread.rseq=0' },
    });

    proc.on('error', (err: NodeJS.ErrnoException) => {
      if (err.code === 'ENOENT') {
        console.error('[Mongod Manager] mongod binary not found (ENOENT). Run: npm run prepare:mongo');
      } else if (err.code === 'EACCES') {
        console.error('[Mongod Manager] mongod binary not executable (EACCES). Check file permissions.');
      } else {
        console.error('[Mongod Manager] Failed to spawn mongod:', err.message);
      }
    });

    // Pipe mongod stdout/stderr line-by-line (same pattern as backend-manager.ts)
    let stdoutBuf = '';
    proc.stdout?.on('data', (data: Buffer) => {
      stdoutBuf += data.toString();
      const lines = stdoutBuf.split('\n');
      stdoutBuf = lines.pop() ?? '';
      lines.forEach(line => { if (line.trim() && shouldLogMongodLine(line)) console.log('[Mongod]', line); });
    });

    let stderrBuf = '';
    proc.stderr?.on('data', (data: Buffer) => {
      stderrBuf += data.toString();
      const lines = stderrBuf.split('\n');
      stderrBuf = lines.pop() ?? '';
      lines.forEach(line => { if (line.trim() && shouldLogMongodLine(line)) console.log('[Mongod]', line); });
    });

    // 5. Set mongodProcess BEFORE Promise.race to avoid the assignment race:
    //    if proc exits between race resolving true and "if (ok) mongodProcess = proc",
    //    the exit handler fires (null), then the assignment sets a dead handle.
    //    By assigning here, stopMongod() can also send SIGTERM during the startup
    //    window — correct behavior on early app quit.
    mongodProcess = proc;

    proc.on('exit', (code) => {
      mongodProcess = null;
      console.error(`[Mongod Manager] mongod exited with code ${code}`);
    });

    // 6. Race: wait for port to open OR process to exit prematurely
    const ok = await Promise.race([pollConnect(), exitSignal(proc)]);
    if (!ok) {
      mongodProcess = null;
      return false;
    }

    console.log(`[Mongod Manager] mongod listening on port ${MONGOD_PORT}`);
    return true;

  } catch (err: any) {
    console.error('[Mongod Manager] Startup error:', err?.message ?? err);
    return false;
  }
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Ensure mongod is running. Concurrent callers share the same in-flight Promise.
 *
 * If called while a previous _doStart() is still in progress, returns the same
 * Promise — no duplicate spawns. The guard resets automatically via .finally().
 */
export function ensureMongodRunning(): Promise<boolean> {
  if (mongodProcess) return Promise.resolve(true);
  if (!startPromise) {
    startPromise = _doStart().finally(() => { startPromise = null; });
  }
  return startPromise;
}

/**
 * Stop the managed mongod instance.
 * No-op if mongod was not spawned by us (mongodProcess is null).
 *
 * If called while startup is in progress, the in-flight process IS killed via
 * SIGTERM (mongodProcess is set immediately after spawn). The OS will also
 * reclaim it on Electron exit regardless.
 */
export function stopMongod(): void {
  if (!mongodProcess) return;
  console.log('[Mongod Manager] Stopping mongod...');
  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', mongodProcess.pid!.toString(), '/f', '/t']);
  } else {
    mongodProcess.kill('SIGTERM');
  }
  mongodProcess = null;
}
