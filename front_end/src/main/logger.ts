import * as fs from 'fs';
import * as path from 'path';
import { ts } from './utils';

const logDir = path.join(__dirname, '../../../logs');
fs.mkdirSync(logDir, { recursive: true });
fs.chmodSync(logDir, 0o700);

const MAX_LOG_FILES = 10;
// Single source of truth: every generated filename MUST match this, and rotation
// only ever touches files that match this. Drift between the two would either
// silently never-rotate or accidentally delete unrelated files.
const LOG_FILE_RE = /^app-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.log$/;

// new Date().toISOString() -> "2026-02-25T09:12:34.567Z"
// We need a filesystem-safe, lexicographically-sortable timestamp.
// Substitutions: T -> _ (separate date/time), : -> - (Windows forbids ':'),
//                . -> - (uniform delimiter before millis), strip trailing 'Z'.
const fileTs = new Date()
  .toISOString()
  .replace('T', '_')
  .replace(/:/g, '-')
  .replace('.', '-')
  .replace('Z', '');
const logFileName = `app-${fileTs}.log`;
// Fail loud at startup if the generator drifts from LOG_FILE_RE; a silent
// mismatch would leave rotation permanently disabled and grow the dir unbounded.
if (!LOG_FILE_RE.test(logFileName)) {
  throw new Error(
    `logger: generated filename "${logFileName}" does not match LOG_FILE_RE`,
  );
}

// Rotate BEFORE creating the new file: post-launch dir = (kept existing) + 1 new,
// so we keep at most MAX_LOG_FILES - 1 of the existing ones to land at MAX_LOG_FILES total.
const existingLogs = fs
  .readdirSync(logDir)
  .filter((name) => LOG_FILE_RE.test(name))
  .sort()
  .reverse(); // lexicographic desc == newest-first, because the ts format is sortable
for (const name of existingLogs.slice(MAX_LOG_FILES - 1)) {
  try {
    fs.unlinkSync(path.join(logDir, name));
  } catch (err) {
    // Don't abort logger init on a single unlink failure, but leave a breadcrumb.
    // Note: console.warn here is still the original (interception is installed below),
    // so this goes to stderr — appropriate, since the failure predates the new log.
    console.warn(`[logger] failed to rotate ${name}:`, err);
  }
}

const logPath = path.join(logDir, logFileName);
const logFd = fs.openSync(logPath, 'w', 0o600);
const logStream = fs.createWriteStream(logPath, { fd: logFd });

function serialize(a: unknown): string {
  if (typeof a === 'string') return a;
  if (a instanceof Error) return a.stack ?? a.message;
  return JSON.stringify(a);
}

function writeToLog(level: string, args: unknown[]): void {
  const message = args.map(serialize).join(' ');
  logStream.write(`[${ts()}] [${level}] ${message}\n`);
}

const origLog = console.log.bind(console);
const origWarn = console.warn.bind(console);
const origError = console.error.bind(console);

console.log = (...args: unknown[]) => {
  origLog(...args);
  writeToLog('LOG', args);
};

console.warn = (...args: unknown[]) => {
  origWarn(...args);
  writeToLog('WARN', args);
};

console.error = (...args: unknown[]) => {
  origError(...args);
  writeToLog('ERROR', args);
};

export function closeLog(): void {
  logStream.end();
}
