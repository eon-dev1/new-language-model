/**
 * Test setup for renderer process (React component) tests.
 *
 * This file runs before each test file and sets up:
 * - localStorage mock (jsdom provides window but localStorage may need configuration)
 * - jest-dom matchers for DOM assertions
 * - Any global test utilities
 */

import '@testing-library/jest-dom';

// localStorage mock for jsdom environment
// jsdom does provide localStorage, but we ensure it's cleared between tests
// and provide a fallback mock if needed

const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string): string | null => {
      return store[key] ?? null;
    },
    setItem: (key: string, value: string): void => {
      store[key] = value;
    },
    removeItem: (key: string): void => {
      delete store[key];
    },
    clear: (): void => {
      store = {};
    },
    get length(): number {
      return Object.keys(store).length;
    },
    key: (index: number): string | null => {
      const keys = Object.keys(store);
      return keys[index] ?? null;
    },
  };
})();

// Only apply mock if localStorage is not available (shouldn't happen in jsdom, but safe)
if (typeof window !== 'undefined' && !window.localStorage) {
  Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
    writable: true,
  });
}

// Clear localStorage before each test to ensure isolation
beforeEach(() => {
  localStorage.clear();
});

// Clean up after all tests
afterAll(() => {
  localStorage.clear();
});
