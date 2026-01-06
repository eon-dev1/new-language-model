/**
 * Test setup file for Vitest
 * 
 * This file runs before all tests and sets up the testing environment
 * for main process credential testing.
 */

import { beforeAll, afterAll } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

// Global test state
let testTempDir: string;

beforeAll(async () => {
  console.log('[Test Setup] Initializing test environment...');
  
  // Create a temporary directory for test files
  testTempDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'nlm-test-'));
  console.log('[Test Setup] Created temp directory:', testTempDir);
});

afterAll(async () => {
  // Clean up temporary files
  if (testTempDir && fs.existsSync(testTempDir)) {
    console.log('[Test Setup] Cleaning up temp directory:', testTempDir);
    await fs.promises.rm(testTempDir, { recursive: true, force: true });
  }
});

// Export for use in tests
export { testTempDir };
