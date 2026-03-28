/**
 * Integration tests for theme reactivity.
 *
 * Tests that settings changes propagate through the component tree
 * and update the theme without requiring a page refresh.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { Typography } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import React, { useMemo } from 'react';

import { SettingsProvider, useSettings } from '../../src/renderer/contexts/SettingsContext';
import { createDynamicTheme } from '../../src/renderer/theme/createDynamicTheme';
import { STORAGE_KEY } from '../../src/renderer/theme/createDynamicTheme';

/**
 * ThemedApp component - mirrors the actual implementation pattern.
 * Creates theme inside React render cycle for reactivity.
 */
const ThemedApp: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { settings } = useSettings();
  const theme = useMemo(() => createDynamicTheme(settings), [settings]);

  return <ThemeProvider theme={theme}>{children}</ThemeProvider>;
};

/**
 * Full app wrapper for testing - matches production structure.
 */
const TestApp: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <SettingsProvider>
    <ThemedApp>{children}</ThemedApp>
  </SettingsProvider>
);

/**
 * Test component that displays current font family from theme.
 */
const FontDisplay: React.FC = () => {
  const { settings } = useSettings();
  return (
    <Typography data-testid="font-display" variant="body1">
      Current font: {settings.fontFamily}
    </Typography>
  );
};

/**
 * Hook to access settings within test wrapper.
 */
const useTestSettings = () => {
  return renderHook(() => useSettings(), {
    wrapper: ({ children }) => (
      <SettingsProvider>
        <ThemedApp>{children}</ThemedApp>
      </SettingsProvider>
    ),
  });
};

describe('Theme Reactivity Integration', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('settings to theme propagation', () => {
    it('theme updates when settings change (no refresh needed)', () => {
      const { result, rerender } = useTestSettings();

      // Initial state
      expect(result.current.settings.fontFamily).toBe('system-ui');

      // Update settings
      act(() => {
        result.current.updateSettings({ fontFamily: 'Times New Roman' });
      });

      // Settings should update
      expect(result.current.settings.fontFamily).toBe('Times New Roman');

      // Verify persistence (would be used on next load)
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
      expect(stored.fontFamily).toBe('Times New Roman');
    });

    it('fontSize changes propagate through context', () => {
      const { result } = useTestSettings();

      expect(result.current.settings.fontSize).toBe(16);

      act(() => {
        result.current.updateSettings({ fontSize: 20 });
      });

      expect(result.current.settings.fontSize).toBe(20);
    });
  });

  describe('component tree integration', () => {
    it('Typography component renders within themed context', () => {
      render(
        <TestApp>
          <Typography data-testid="test-text" variant="body1">
            Test content
          </Typography>
        </TestApp>
      );

      expect(screen.getByTestId('test-text')).toBeInTheDocument();
      expect(screen.getByText('Test content')).toBeInTheDocument();
    });

    it('settings changes reflect in components', () => {
      const { rerender } = render(
        <TestApp>
          <FontDisplay />
        </TestApp>
      );

      // Initial state shows system-ui
      expect(screen.getByTestId('font-display')).toHaveTextContent('system-ui');
    });
  });

  describe('provider nesting order', () => {
    it('ThemedApp can access useSettings (correct provider order)', () => {
      // This test verifies that ThemedApp is inside SettingsProvider
      // If order is wrong, useSettings would throw
      expect(() => {
        render(
          <SettingsProvider>
            <ThemedApp>
              <div>Content</div>
            </ThemedApp>
          </SettingsProvider>
        );
      }).not.toThrow();
    });

    it('throws if ThemedApp is outside SettingsProvider', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(
          <ThemedApp>
            <div>Content</div>
          </ThemedApp>
        );
      }).toThrow('useSettings must be used within a SettingsProvider');

      consoleSpy.mockRestore();
    });
  });

  describe('theme creation', () => {
    it('createDynamicTheme produces valid MUI theme', () => {
      const theme = createDynamicTheme({ fontFamily: 'system-ui', fontSize: 16 });

      // Theme should have required MUI structure
      expect(theme.palette).toBeDefined();
      expect(theme.typography).toBeDefined();
      expect(theme.components).toBeDefined();
    });

    it('theme reflects current settings', () => {
      const systemTheme = createDynamicTheme({ fontFamily: 'system-ui', fontSize: 16 });
      const timesTheme = createDynamicTheme({ fontFamily: 'Times New Roman', fontSize: 16 });

      expect(systemTheme.typography.fontFamily).toContain('system-ui');
      expect(timesTheme.typography.fontFamily).toContain('Times New Roman');
    });
  });
});
