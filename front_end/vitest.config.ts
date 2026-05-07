import { defineConfig } from 'vitest/config';

export default defineConfig({
  // Replace import.meta.env vars at transform time so api.ts loads in tests.
  define: {
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://localhost:8221'),
  },
  test: {
    // Use Node.js environment for main process testing
    environment: 'node',
    
    // Enable global test functions (describe, it, expect)
    globals: true,
    
    // Test file patterns
    include: ['tests/**/*.test.{ts,js}', 'src/**/*.test.ts'],
    
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
