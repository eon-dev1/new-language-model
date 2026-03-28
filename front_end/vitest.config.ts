import { defineConfig } from 'vitest/config';

/**
 * Vitest configuration for testing Electron main process functionality.
 * 
 * This configuration is optimized for testing Node.js-based main process code
 * including file system operations and credential loading.
 */
export default defineConfig({
  test: {
    // Use Node.js environment for main process testing
    environment: 'node',
    
    // Enable global test functions (describe, it, expect)
    globals: true,
    
    // Test file patterns
    include: ['tests/**/*.test.ts', 'src/**/*.test.ts'],
    
    // Longer timeout for file operations and IPC testing
    testTimeout: 10000,
    
    // Setup files to run before tests
    setupFiles: ['./tests/setup.ts'],
    
    // Coverage configuration
    coverage: {
      provider: 'v8',
      include: ['src/main/**/*.ts'],
      exclude: ['src/main/**/*.test.ts'],
      reporter: ['text', 'html', 'lcov'],
    },
  },
});
