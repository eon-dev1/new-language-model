import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/**
 * Vitest configuration for testing React renderer process components.
 *
 * Uses jsdom environment to simulate browser DOM for React component testing.
 * Separate from the main vitest.config.ts which uses Node environment for main process.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    // Use jsdom environment for React component testing
    environment: 'jsdom',

    // Enable global test functions (describe, it, expect)
    globals: true,

    // Test file patterns - only renderer tests
    include: ['tests/renderer/**/*.test.{ts,tsx}'],

    // Setup files for renderer tests
    setupFiles: ['./tests/renderer/setup.ts'],

    // Longer timeout for component testing
    testTimeout: 10000,

    // Coverage configuration
    coverage: {
      provider: 'v8',
      include: ['src/renderer/**/*.{ts,tsx}'],
      exclude: ['src/renderer/**/*.test.{ts,tsx}'],
      reporter: ['text', 'html', 'lcov'],
    },
  },
});
