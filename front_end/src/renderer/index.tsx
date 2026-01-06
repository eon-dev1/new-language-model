// src/renderer/index.tsx
import React, { useMemo } from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { App } from './app';
import { SettingsProvider, useSettings } from './contexts/SettingsContext';
import { createDynamicTheme } from './theme/createDynamicTheme';

/**
 * ThemedApp - Wrapper that creates dynamic theme based on settings.
 *
 * CRITICAL: This component must be INSIDE SettingsProvider because it uses useSettings().
 * CssBaseline must be INSIDE ThemeProvider to receive dynamic font.
 */
const ThemedApp: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { settings } = useSettings();
  const theme = useMemo(() => createDynamicTheme(settings), [settings]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
};

const container = document.getElementById('root');
if (!container) throw new Error('Root element not found!');
const root = createRoot(container);

/**
 * App structure:
 * SettingsProvider (context boundary)
 *   └─ ThemedApp (creates dynamic theme from settings)
 *        └─ ThemeProvider (MUI theme)
 *             └─ CssBaseline (applies font to <body>)
 *             └─ App (main application)
 */
root.render(
  <SettingsProvider>
    <ThemedApp>
      <App />
    </ThemedApp>
  </SettingsProvider>
);
