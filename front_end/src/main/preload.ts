// preload.ts

import { contextBridge, ipcRenderer } from 'electron';

/**
 * Secure API for renderer process communication with main process.
 * This exposes only necessary functions while maintaining security isolation.
 */
contextBridge.exposeInMainWorld('api', {
  // Window control functions
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),

  // Folder selection for imports
  selectFolder: () => ipcRenderer.invoke('select-folder'),

  // Open a URL in the system's default browser (main process enforces https:// only)
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
});

window.addEventListener('DOMContentLoaded', () => {
  // You can expose additional APIs here if needed in the future.
});