// devtools-manager.test.ts
// Tests for DevTools state management functions

import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { BrowserWindow } from 'electron';

// Only mock electron - NOT the module under test
vi.mock('electron', () => ({
  BrowserWindow: vi.fn()
}));

// Import REAL functions from the module under test
import {
  getStartupPreference,
  initDevToolsManager,
  toggleDevTools,
  getDevToolsState,
  setDevToolsState,
  syncDevToolsState
} from '../src/main/devtools-manager';

describe('DevTools Manager', () => {
  // Helper to create mock window with configurable initial state
  const createMockWindow = (isOpen = false) => ({
    webContents: {
      isDevToolsOpened: vi.fn().mockReturnValue(isOpen),
      openDevTools: vi.fn(),
      closeDevTools: vi.fn(),
      on: vi.fn(),
      emit: vi.fn()
    }
  } as unknown as BrowserWindow);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getStartupPreference', () => {
    it('should return a boolean startup preference', () => {
      const result = getStartupPreference();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('initDevToolsManager', () => {
    it('should return the startup preference state', () => {
      const result = initDevToolsManager();
      expect(result).toBe(getStartupPreference());
    });

    it('should set up event listeners when window provided', () => {
      const mockWindow = createMockWindow();
      initDevToolsManager(mockWindow);
      expect(mockWindow.webContents.on).toHaveBeenCalledWith('devtools-opened', expect.any(Function));
      expect(mockWindow.webContents.on).toHaveBeenCalledWith('devtools-closed', expect.any(Function));
    });
  });

  describe('toggleDevTools', () => {
    it('should open DevTools if currently closed', () => {
      const mockWindow = createMockWindow(false);
      const result = toggleDevTools(mockWindow);

      expect(mockWindow.webContents.isDevToolsOpened).toHaveBeenCalled();
      expect(mockWindow.webContents.openDevTools).toHaveBeenCalledWith({ mode: 'detach' });
      expect(mockWindow.webContents.closeDevTools).not.toHaveBeenCalled();
      expect(result).toBe(true);
    });

    it('should close DevTools if currently open', () => {
      const mockWindow = createMockWindow(true);
      const result = toggleDevTools(mockWindow);

      expect(mockWindow.webContents.isDevToolsOpened).toHaveBeenCalled();
      expect(mockWindow.webContents.closeDevTools).toHaveBeenCalled();
      expect(mockWindow.webContents.openDevTools).not.toHaveBeenCalled();
      expect(result).toBe(false);
    });

    it('should return false if window is null', () => {
      const result = toggleDevTools(null);
      expect(result).toBe(false);
    });
  });

  describe('getDevToolsState', () => {
    it('should return current state after toggle opens DevTools', () => {
      const mockWindow = createMockWindow(false);
      toggleDevTools(mockWindow); // Opens DevTools, sets state to true
      expect(getDevToolsState()).toBe(true);
    });

    it('should return current state after toggle closes DevTools', () => {
      const mockWindow = createMockWindow(true);
      toggleDevTools(mockWindow); // Closes DevTools, sets state to false
      expect(getDevToolsState()).toBe(false);
    });
  });

  describe('setDevToolsState', () => {
    it('should open DevTools when setting state to true and currently closed', () => {
      const mockWindow = createMockWindow(false);
      setDevToolsState(true, mockWindow);

      expect(mockWindow.webContents.openDevTools).toHaveBeenCalledWith({ mode: 'detach' });
      expect(mockWindow.webContents.closeDevTools).not.toHaveBeenCalled();
    });

    it('should close DevTools when setting state to false and currently open', () => {
      const mockWindow = createMockWindow(true);
      setDevToolsState(false, mockWindow);

      expect(mockWindow.webContents.closeDevTools).toHaveBeenCalled();
      expect(mockWindow.webContents.openDevTools).not.toHaveBeenCalled();
    });

    it('should do nothing if window is null', () => {
      // Should not throw an error
      expect(() => setDevToolsState(true, null)).not.toThrow();
    });

    it('should not open DevTools if already open', () => {
      const mockWindow = createMockWindow(true);
      setDevToolsState(true, mockWindow);

      expect(mockWindow.webContents.openDevTools).not.toHaveBeenCalled();
    });

    it('should not close DevTools if already closed', () => {
      const mockWindow = createMockWindow(false);
      setDevToolsState(false, mockWindow);

      expect(mockWindow.webContents.closeDevTools).not.toHaveBeenCalled();
    });
  });

  describe('syncDevToolsState', () => {
    it('should sync with actual window state when open', () => {
      const mockWindow = createMockWindow(true);
      const result = syncDevToolsState(mockWindow);

      expect(mockWindow.webContents.isDevToolsOpened).toHaveBeenCalled();
      expect(result).toBe(true);
    });

    it('should sync with actual window state when closed', () => {
      const mockWindow = createMockWindow(false);
      const result = syncDevToolsState(mockWindow);

      expect(mockWindow.webContents.isDevToolsOpened).toHaveBeenCalled();
      expect(result).toBe(false);
    });

    it('should return false if window is null', () => {
      const result = syncDevToolsState(null);
      expect(result).toBe(false);
    });
  });
});
