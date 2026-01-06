// backend-manager.ts
// Manages the FastAPI backend lifecycle from Electron

import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as http from 'http';

const BACKEND_PORT = 8221;
const BACKEND_HOST = '127.0.0.1';
const HEALTH_ENDPOINT = '/api/check-connection';
const MAX_RETRIES = 30;  // 30 seconds max wait
const RETRY_INTERVAL = 1000;  // 1 second between retries

let backendProcess: ChildProcess | null = null;

/**
 * Check if the backend server is running and responding
 */
export function checkBackendRunning(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.request(
      {
        hostname: BACKEND_HOST,
        port: BACKEND_PORT,
        path: HEALTH_ENDPOINT,
        method: 'GET',
        timeout: 2000,
      },
      (res) => {
        resolve(res.statusCode === 200);
      }
    );

    req.on('error', () => {
      resolve(false);
    });

    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });

    req.end();
  });
}

/**
 * Start the backend server as a child process
 */
export function startBackend(): ChildProcess {
  // Get path to back_end directory (relative to front_end)
  const backendDir = path.resolve(__dirname, '../../../back_end');

  console.log('[Backend Manager] Starting backend server...');
  console.log('[Backend Manager] Backend directory:', backendDir);

  // Use Python from the virtual environment
  const venvPython = process.platform === 'win32'
    ? path.join(backendDir, 'nlm_backend_venv', 'Scripts', 'python.exe')
    : path.join(backendDir, 'nlm_backend_venv', 'bin', 'python');

  console.log('[Backend Manager] Using Python:', venvPython);

  backendProcess = spawn(venvPython, ['main.py'], {
    cwd: backendDir,
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false,
  });

  // Log backend stdout
  backendProcess.stdout?.on('data', (data: Buffer) => {
    const lines = data.toString().trim().split('\n');
    lines.forEach(line => {
      console.log('[Backend]', line);
    });
  });

  // Log backend stderr
  backendProcess.stderr?.on('data', (data: Buffer) => {
    const lines = data.toString().trim().split('\n');
    lines.forEach(line => {
      console.error('[Backend Error]', line);
    });
  });

  backendProcess.on('error', (err) => {
    console.error('[Backend Manager] Failed to start backend:', err.message);
  });

  backendProcess.on('exit', (code, signal) => {
    console.log(`[Backend Manager] Backend exited with code ${code}, signal ${signal}`);
    backendProcess = null;
  });

  return backendProcess;
}

/**
 * Wait for the backend to become ready
 */
async function waitForBackend(maxRetries: number = MAX_RETRIES): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    const isRunning = await checkBackendRunning();
    if (isRunning) {
      console.log(`[Backend Manager] Backend is ready (took ${i + 1} seconds)`);
      return true;
    }
    console.log(`[Backend Manager] Waiting for backend... (${i + 1}/${maxRetries})`);
    await new Promise(resolve => setTimeout(resolve, RETRY_INTERVAL));
  }
  return false;
}

/**
 * Ensure the backend is running, starting it if necessary
 */
export async function ensureBackendRunning(): Promise<boolean> {
  console.log('[Backend Manager] Checking if backend is already running...');

  // First check if backend is already running
  const alreadyRunning = await checkBackendRunning();
  if (alreadyRunning) {
    console.log('[Backend Manager] Backend is already running');
    return true;
  }

  console.log('[Backend Manager] Backend not running, starting it...');

  // Start the backend
  startBackend();

  // Wait for it to be ready
  const isReady = await waitForBackend();

  if (!isReady) {
    console.error('[Backend Manager] Backend failed to start within timeout');
    return false;
  }

  return true;
}

/**
 * Stop the backend server if we started it
 */
export function stopBackend(): void {
  if (backendProcess) {
    console.log('[Backend Manager] Stopping backend server...');

    // On Windows, we need to kill the process tree
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', backendProcess.pid!.toString(), '/f', '/t']);
    } else {
      backendProcess.kill('SIGTERM');
    }

    backendProcess = null;
  }
}

/**
 * Check if we started the backend (vs it was already running)
 */
export function isBackendManagedByUs(): boolean {
  return backendProcess !== null;
}