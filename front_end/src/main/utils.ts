import * as path from 'path';

/**
 * Returns the last N segments of a path to avoid leaking full filesystem layout.
 * e.g. shortPath('/home/user/projects/nlm/back_end') → 'nlm/back_end'
 */
export function shortPath(p: string, segments = 2): string {
  return p.split(path.sep).slice(-segments).join(path.sep);
}

/**
 * ISO timestamp for log prefixes.
 * e.g. '2026-02-25 09:12:34.567'
 */
export function ts(): string {
  return new Date().toISOString().replace('T', ' ').substring(0, 23);
}
