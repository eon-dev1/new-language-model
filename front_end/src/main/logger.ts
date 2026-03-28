import * as fs from 'fs';
import * as path from 'path';
import { ts } from './utils';

const logDir = path.join(__dirname, '../../../logs');
fs.mkdirSync(logDir, { recursive: true });
fs.chmodSync(logDir, 0o700);

const logPath = path.join(logDir, 'app.log');
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
