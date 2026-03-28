/**
 * Tests for SettingsDialog - Dialog component for font settings.
 *
 * TDD: These tests are written FIRST (RED), then implementation follows (GREEN).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@mui/material/styles';
import React from 'react';

import { SettingsDialog } from '../../src/renderer/components/SettingsDialog';
import { SettingsProvider, useSettings } from '../../src/renderer/contexts/SettingsContext';
import { createDynamicTheme } from '../../src/renderer/theme/createDynamicTheme';

// Helper to wrap component with required providers
const renderWithProviders = (ui: React.ReactElement) => {
  const theme = createDynamicTheme({ fontFamily: 'system-ui', fontSize: 16 });
  return render(
    <SettingsProvider>
      <ThemeProvider theme={theme}>
        {ui}
      </ThemeProvider>
    </SettingsProvider>
  );
};

// Helper component to read and display current settings
const SettingsReader: React.FC = () => {
  const { settings } = useSettings();
  return (
    <div data-testid="settings-reader">
      <span data-testid="current-font-family">{settings.fontFamily}</span>
      <span data-testid="current-font-size">{settings.fontSize}</span>
    </div>
  );
};

describe('SettingsDialog', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('visibility', () => {
    it('renders dialog content when open=true', () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    it('does not render dialog content when open=false', () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={false} onClose={onClose} />
      );

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  describe('font family dropdown', () => {
    it('renders font family select with label', () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      expect(screen.getByLabelText(/font family/i)).toBeInTheDocument();
    });

    it('has System Default option', async () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      // Open the select dropdown
      const select = screen.getByLabelText(/font family/i);
      await userEvent.click(select);

      // Check for option in listbox
      expect(screen.getByRole('option', { name: /system default/i })).toBeInTheDocument();
    });

    it('has Times New Roman option', async () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      const select = screen.getByLabelText(/font family/i);
      await userEvent.click(select);

      expect(screen.getByRole('option', { name: /times new roman/i })).toBeInTheDocument();
    });
  });

  describe('font size slider', () => {
    it('renders font size slider', () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      expect(screen.getByRole('slider')).toBeInTheDocument();
    });

    it('slider has min value of 12', () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('aria-valuemin', '12');
    });

    it('slider has max value of 24', () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('aria-valuemax', '24');
    });

    it('displays current font size value', () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      // Default is 16px
      expect(screen.getByText(/16\s*px/i)).toBeInTheDocument();
    });
  });

  describe('settings updates', () => {
    it('changing font family updates context', async () => {
      const onClose = vi.fn();
      renderWithProviders(
        <>
          <SettingsDialog open={true} onClose={onClose} />
          <SettingsReader />
        </>
      );

      // Initial value
      expect(screen.getByTestId('current-font-family')).toHaveTextContent('system-ui');

      // Open select and choose Times New Roman
      const select = screen.getByLabelText(/font family/i);
      await userEvent.click(select);
      await userEvent.click(screen.getByRole('option', { name: /times new roman/i }));

      // Verify context updated
      expect(screen.getByTestId('current-font-family')).toHaveTextContent('Times New Roman');
    });

    it('changing font size updates context', async () => {
      const onClose = vi.fn();
      renderWithProviders(
        <>
          <SettingsDialog open={true} onClose={onClose} />
          <SettingsReader />
        </>
      );

      // Initial value
      expect(screen.getByTestId('current-font-size')).toHaveTextContent('16');

      // Change slider value using fireEvent.change on the underlying input
      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: 20 } });

      // Should now be 20
      expect(screen.getByTestId('current-font-size')).toHaveTextContent('20');
    });
  });

  describe('reset button', () => {
    it('renders reset button', () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
    });

    it('clicking reset restores default settings', async () => {
      // Pre-set non-default values in localStorage
      localStorage.setItem('nlm-app-settings', JSON.stringify({
        fontFamily: 'Times New Roman',
        fontSize: 20,
      }));

      const onClose = vi.fn();
      renderWithProviders(
        <>
          <SettingsDialog open={true} onClose={onClose} />
          <SettingsReader />
        </>
      );

      // Verify non-default values loaded
      expect(screen.getByTestId('current-font-family')).toHaveTextContent('Times New Roman');
      expect(screen.getByTestId('current-font-size')).toHaveTextContent('20');

      // Click reset
      await userEvent.click(screen.getByRole('button', { name: /reset/i }));

      // Verify defaults restored
      expect(screen.getByTestId('current-font-family')).toHaveTextContent('system-ui');
      expect(screen.getByTestId('current-font-size')).toHaveTextContent('16');
    });
  });

  describe('close functionality', () => {
    it('calls onClose when close button is clicked', async () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      // Find and click close button (usually has aria-label or is an IconButton)
      const closeButton = screen.getByRole('button', { name: /close/i });
      await userEvent.click(closeButton);

      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('preview', () => {
    it('shows preview text', () => {
      const onClose = vi.fn();
      renderWithProviders(
        <SettingsDialog open={true} onClose={onClose} />
      );

      // Should have some preview text like "The quick brown fox..."
      expect(screen.getByText(/quick brown fox/i)).toBeInTheDocument();
    });
  });
});
