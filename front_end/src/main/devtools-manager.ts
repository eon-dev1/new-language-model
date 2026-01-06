// devtools-manager.ts
// Manages DevTools state and toggling

import { BrowserWindow } from 'electron';

// Simple boolean to control automatic DevTools opening on startup
// Set to true to auto-open DevTools, false to keep closed
const AUTO_OPEN_DEVTOOLS_ON_STARTUP = true;

// Track DevTools state
let isDevToolsOpen = false;

// Reference to the main window for event handling
let mainWindowRef: BrowserWindow | null = null;

/**
 * Get the startup preference for DevTools
 * @returns True if DevTools should auto-open on startup, false otherwise
 */
export function getStartupPreference(): boolean {
  return AUTO_OPEN_DEVTOOLS_ON_STARTUP;
}

/**
 * Initialize DevTools manager using startup preference
 * @param mainWindow Optional main window reference for event handling
 * @returns The current DevTools state (open or closed)
 */
export function initDevToolsManager(mainWindow?: BrowserWindow): boolean {
  // Use the boolean constant instead of loading from file
  isDevToolsOpen = AUTO_OPEN_DEVTOOLS_ON_STARTUP;
  
  // Store reference to main window if provided
  if (mainWindow) {
    mainWindowRef = mainWindow;
    setupDevToolsEventListeners(mainWindow);
  }
  
  return isDevToolsOpen;
}

/**
 * Set up event listeners for DevTools state changes
 * @param mainWindow The main BrowserWindow instance
 */
function setupDevToolsEventListeners(mainWindow: BrowserWindow): void {
  // Listen for DevTools opened event
  mainWindow.webContents.on('devtools-opened', () => {
    console.log('DevTools opened externally');
    handleDevToolsStateChange(true);
  });
  
  // Listen for DevTools closed event
  mainWindow.webContents.on('devtools-closed', () => {
    console.log('DevTools closed externally');
    handleDevToolsStateChange(false);
  });
}

/**
 * Handle DevTools state changes from external events
 * @param isOpen The new DevTools state
 */
function handleDevToolsStateChange(isOpen: boolean): void {
  // Update internal state
  isDevToolsOpen = isOpen;
  
  // Emit an event for menu updates
  if (mainWindowRef) {
    mainWindowRef.webContents.emit('devtools-state-changed', isDevToolsOpen);
  }
}

/**
 * Toggle DevTools visibility for the given window
 * @param mainWindow The main BrowserWindow instance
 * @returns Current state of DevTools after toggling
 */
export function toggleDevTools(mainWindow: BrowserWindow | null): boolean {
  if (!mainWindow) return false;
  
  if (mainWindow.webContents.isDevToolsOpened()) {
    mainWindow.webContents.closeDevTools();
    isDevToolsOpen = false;
  } else {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
    isDevToolsOpen = true;
  }
  
  return isDevToolsOpen;
}

/**
 * Get the current DevTools state
 * @returns True if DevTools is open, false otherwise
 */
export function getDevToolsState(): boolean {
  return isDevToolsOpen;
}

/**
 * Set the DevTools state directly
 * @param state The state to set (true for open, false for closed)
 * @param mainWindow The main BrowserWindow instance
 */
export function setDevToolsState(state: boolean, mainWindow: BrowserWindow | null): void {
  if (!mainWindow) return;
  
  if (state && !mainWindow.webContents.isDevToolsOpened()) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else if (!state && mainWindow.webContents.isDevToolsOpened()) {
    mainWindow.webContents.closeDevTools();
  }
  
  isDevToolsOpen = state;
}

/**
 * Update DevTools state based on actual window state
 * @param mainWindow The main BrowserWindow instance
 * @returns The current DevTools state
 */
export function syncDevToolsState(mainWindow: BrowserWindow | null): boolean {
  if (!mainWindow) return false;
  
  isDevToolsOpen = mainWindow.webContents.isDevToolsOpened();
  return isDevToolsOpen;
}
