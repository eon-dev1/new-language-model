/**
 * Type definitions for Electron API and environment variables.
 */

interface Window {
  api: {
    // Window controls
    minimize: () => void;
    maximize: () => void;
    close: () => void;

    // DevTools
    openDevTools: () => void;

    // Folder selection for imports
    selectFolder: () => Promise<string | null>;
  };
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}