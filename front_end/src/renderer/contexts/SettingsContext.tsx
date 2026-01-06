/**
 * Settings Context - Manages app settings state with localStorage persistence.
 *
 * Provides:
 * - settings: Current AppSettings
 * - updateSettings: Merge partial updates and persist
 * - resetSettings: Restore defaults
 */

import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import {
  type AppSettings,
  DEFAULT_SETTINGS,
  STORAGE_KEY,
} from '../theme/createDynamicTheme';

// Re-export for convenience
export type { AppSettings };

/**
 * Context value interface.
 */
export interface SettingsContextType {
  settings: AppSettings;
  updateSettings: (partial: Partial<AppSettings>) => void;
  resetSettings: () => void;
}

/**
 * Load settings from localStorage with error handling.
 * Returns defaults if localStorage is empty, corrupted, or contains invalid data.
 */
const loadSettings = (): AppSettings => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return DEFAULT_SETTINGS;
    }

    const parsed = JSON.parse(stored);

    // Validate parsed data is an object with expected shape
    if (
      parsed &&
      typeof parsed === 'object' &&
      typeof parsed.fontFamily === 'string' &&
      typeof parsed.fontSize === 'number'
    ) {
      return parsed as AppSettings;
    }

    return DEFAULT_SETTINGS;
  } catch {
    // JSON.parse failed - corrupted data
    return DEFAULT_SETTINGS;
  }
};

/**
 * Save settings to localStorage.
 */
const saveSettings = (settings: AppSettings): void => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // localStorage might be full or disabled - fail silently
    console.warn('Failed to save settings to localStorage');
  }
};

// Create context with undefined default (forces provider usage)
const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

/**
 * Settings Provider component.
 * Wraps app to provide settings context.
 */
export const SettingsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [settings, setSettings] = useState<AppSettings>(loadSettings);

  /**
   * Update settings with partial values and persist.
   */
  const updateSettings = useCallback((partial: Partial<AppSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...partial };
      saveSettings(next);
      return next;
    });
  }, []);

  /**
   * Reset to default settings and persist.
   */
  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
    saveSettings(DEFAULT_SETTINGS);
  }, []);

  const value: SettingsContextType = {
    settings,
    updateSettings,
    resetSettings,
  };

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  );
};

/**
 * Hook to access settings context.
 * Must be used within SettingsProvider.
 */
export const useSettings = (): SettingsContextType => {
  const context = useContext(SettingsContext);

  if (context === undefined) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }

  return context;
};
