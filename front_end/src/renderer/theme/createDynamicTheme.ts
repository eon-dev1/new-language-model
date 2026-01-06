/**
 * Dynamic theme factory for font settings.
 *
 * Creates MUI theme based on user settings while preserving
 * existing palette and component customizations.
 */

import { createTheme, type Theme, type ThemeOptions } from '@mui/material/styles';

/**
 * User-configurable settings for appearance.
 */
export interface AppSettings {
  fontFamily: 'system-ui' | 'Times New Roman';
  fontSize: number; // 12-24
}

/**
 * Default settings used when no saved settings exist.
 */
export const DEFAULT_SETTINGS: AppSettings = {
  fontFamily: 'system-ui',
  fontSize: 16,
};

/**
 * localStorage key for persisting settings.
 */
export const STORAGE_KEY = 'nlm-app-settings';

/**
 * Maps font family setting to CSS font stack.
 */
const getFontStack = (fontFamily: AppSettings['fontFamily']): string =>
  fontFamily === 'system-ui'
    ? 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    : '"Times New Roman", Times, Georgia, serif';

/**
 * Base theme options extracted from the original futuristicTheme.
 * These non-typography elements are preserved across font changes.
 */
const BASE_THEME_OPTIONS: ThemeOptions = {
  palette: {
    mode: 'dark',
    background: {
      default: '#000000',
      paper: '#222222',
    },
    primary: {
      main: '#C0C0C0',
      dark: '#A0A0A0',
    },
    text: {
      primary: '#FFFFFF',
      secondary: '#CCCCCC',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          boxShadow: '0 0 5px rgba(255, 255, 255, 0.2)',
          textTransform: 'none' as const,
          fontWeight: 600,
          '&:hover': {
            boxShadow: '0 0 10px rgba(255, 255, 255, 0.5)',
            transform: 'scale(1.05)',
            transition: 'all 0.3s ease',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          background: 'linear-gradient(135deg, #222222, #333333)',
          boxShadow: '0 0 15px rgba(255, 255, 255, 0.05)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
        },
      },
    },
  },
};

/**
 * Creates a dynamic MUI theme based on user settings.
 *
 * @param settings - User's font preferences
 * @returns MUI Theme with dynamic typography and preserved base styles
 */
export const createDynamicTheme = (settings: AppSettings): Theme => {
  const fontStack = getFontStack(settings.fontFamily);
  const scale = settings.fontSize / 16; // 16px baseline → scale factor

  return createTheme({
    ...BASE_THEME_OPTIONS,
    typography: {
      fontFamily: fontStack,
      h1: {
        fontFamily: fontStack,
        fontSize: `${3 * scale}rem`,
        fontWeight: 700,
        textShadow: '0 0 5px rgba(255, 255, 255, 0.5)',
      },
      h2: {
        fontFamily: fontStack,
        fontSize: `${2 * scale}rem`,
        fontWeight: 600,
      },
      h3: {
        fontFamily: fontStack,
        fontSize: `${1.5 * scale}rem`,
      },
      h4: {
        fontFamily: fontStack,
        fontSize: `${1.5 * scale}rem`,
      },
      h5: {
        fontFamily: fontStack,
        fontSize: `${1.25 * scale}rem`,
      },
      h6: {
        fontFamily: fontStack,
        fontSize: `${1 * scale}rem`,
      },
      body1: {
        fontFamily: fontStack,
        fontSize: `${1 * scale}rem`,
      },
      body2: {
        fontFamily: fontStack,
        fontSize: `${0.875 * scale}rem`,
      },
      subtitle1: {
        fontFamily: fontStack,
        fontSize: `${1 * scale}rem`,
      },
      subtitle2: {
        fontFamily: fontStack,
        fontSize: `${0.875 * scale}rem`,
      },
      caption: {
        fontFamily: fontStack,
        fontSize: `${0.75 * scale}rem`,
      },
      button: {
        fontFamily: fontStack,
        fontSize: `${0.875 * scale}rem`,
      },
    },
  });
};
