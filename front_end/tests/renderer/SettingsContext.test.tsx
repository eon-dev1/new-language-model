/**
 * Tests for SettingsContext - React context for managing app settings.
 *
 * TDD: These tests are written FIRST (RED), then implementation follows (GREEN).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import {
  SettingsProvider,
  useSettings,
  type AppSettings,
} from '../../src/renderer/contexts/SettingsContext';
import { STORAGE_KEY, DEFAULT_SETTINGS } from '../../src/renderer/theme/createDynamicTheme';

// Helper to render hook with provider
const renderSettingsHook = () => {
  return renderHook(() => useSettings(), {
    wrapper: SettingsProvider,
  });
};

describe('SettingsContext', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('initialization', () => {
    it('provides default settings when localStorage is empty', () => {
      const { result } = renderSettingsHook();

      expect(result.current.settings.fontFamily).toBe('system-ui');
      expect(result.current.settings.fontSize).toBe(16);
    });

    it('loads saved settings from localStorage on mount', () => {
      const savedSettings: AppSettings = {
        fontFamily: 'Times New Roman',
        fontSize: 20,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(savedSettings));

      const { result } = renderSettingsHook();

      expect(result.current.settings.fontFamily).toBe('Times New Roman');
      expect(result.current.settings.fontSize).toBe(20);
    });

    it('returns defaults when localStorage contains corrupted JSON', () => {
      localStorage.setItem(STORAGE_KEY, 'not-valid-json{{{');

      const { result } = renderSettingsHook();

      // Should not throw, should return defaults
      expect(result.current.settings.fontFamily).toBe('system-ui');
      expect(result.current.settings.fontSize).toBe(16);
    });

    it('returns defaults when localStorage contains null', () => {
      localStorage.setItem(STORAGE_KEY, 'null');

      const { result } = renderSettingsHook();

      expect(result.current.settings.fontFamily).toBe('system-ui');
      expect(result.current.settings.fontSize).toBe(16);
    });
  });

  describe('updateSettings', () => {
    it('merges partial updates (fontSize only)', () => {
      const { result } = renderSettingsHook();

      act(() => {
        result.current.updateSettings({ fontSize: 20 });
      });

      expect(result.current.settings.fontSize).toBe(20);
      expect(result.current.settings.fontFamily).toBe('system-ui'); // unchanged
    });

    it('merges partial updates (fontFamily only)', () => {
      const { result } = renderSettingsHook();

      act(() => {
        result.current.updateSettings({ fontFamily: 'Times New Roman' });
      });

      expect(result.current.settings.fontFamily).toBe('Times New Roman');
      expect(result.current.settings.fontSize).toBe(16); // unchanged
    });

    it('persists to localStorage after update', () => {
      const { result } = renderSettingsHook();

      act(() => {
        result.current.updateSettings({ fontSize: 24 });
      });

      const stored = localStorage.getItem(STORAGE_KEY);
      expect(stored).not.toBeNull();

      const parsed = JSON.parse(stored!);
      expect(parsed.fontSize).toBe(24);
      expect(parsed.fontFamily).toBe('system-ui');
    });

    it('updates multiple settings at once', () => {
      const { result } = renderSettingsHook();

      act(() => {
        result.current.updateSettings({
          fontFamily: 'Times New Roman',
          fontSize: 18,
        });
      });

      expect(result.current.settings.fontFamily).toBe('Times New Roman');
      expect(result.current.settings.fontSize).toBe(18);
    });
  });

  describe('resetSettings', () => {
    it('restores default settings', () => {
      const { result } = renderSettingsHook();

      // First, change settings
      act(() => {
        result.current.updateSettings({
          fontFamily: 'Times New Roman',
          fontSize: 24,
        });
      });

      // Verify changed
      expect(result.current.settings.fontFamily).toBe('Times New Roman');
      expect(result.current.settings.fontSize).toBe(24);

      // Reset
      act(() => {
        result.current.resetSettings();
      });

      // Verify defaults restored
      expect(result.current.settings.fontFamily).toBe('system-ui');
      expect(result.current.settings.fontSize).toBe(16);
    });

    it('clears localStorage after reset', () => {
      const { result } = renderSettingsHook();

      // Change and persist
      act(() => {
        result.current.updateSettings({ fontSize: 20 });
      });
      expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull();

      // Reset
      act(() => {
        result.current.resetSettings();
      });

      // localStorage should be cleared or contain defaults
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.fontFamily).toBe('system-ui');
        expect(parsed.fontSize).toBe(16);
      }
    });
  });

  describe('context requirements', () => {
    it('throws error when useSettings is used outside provider', () => {
      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        renderHook(() => useSettings());
      }).toThrow();

      consoleSpy.mockRestore();
    });
  });
});
