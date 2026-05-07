/**
 * Type definitions for Electron API and environment variables.
 */

interface Window {
  api: {
    // Window controls
    minimize: () => void;
    maximize: () => void;
    close: () => void;

    // Folder selection for imports
    selectFolder: () => Promise<string | null>;
  };
}

