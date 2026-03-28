// src/renderer/types.d.ts

/**
 * Type declarations for custom window properties exposed by preload.
 * This file helps TypeScript recognize 'api' on the window object
 * without causing compilation errors in the renderer process.
 */

interface Window {
  api: {
    /**
     * Minimize the main window.
     */
    minimize: () => void;
    /**
     * Maximize or restore the main window.
     */
    maximize: () => void;
    /**
     * Close the main window.
     */
    close: () => void;
    /**
     * Open native folder selection dialog.
     * @returns Selected folder path, or null if cancelled
     */
    selectFolder: () => Promise<string | null>;
  };
}