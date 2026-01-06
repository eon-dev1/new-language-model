// main.ts

import { app, BrowserWindow, Menu, MenuItemConstructorOptions, ipcMain, dialog } from 'electron';
import * as path from 'path';
import { getDevToolsState, getStartupPreference, toggleDevTools as toggleDevToolsState, initDevToolsManager } from './devtools-manager';
import { ensureBackendRunning, stopBackend, isBackendManagedByUs } from './backend-manager';

// Initialize DevTools manager and get saved state
// We'll pass the mainWindow after it's created

let mainWindow: BrowserWindow | null = null;

/**
 * Creates the application main menu
 * @returns The built menu from template
 */
function createMainMenu() {
  const devToolsOpen = getDevToolsState();
  console.log("Creating main menu - DevTools state:", devToolsOpen);
  
  const template: MenuItemConstructorOptions[] = [
    {
      label: 'File',
      submenu: [{ role: 'quit' }],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'copy' },
        { role: 'paste' },
      ],
    },
    {
      label: 'View',
      click: () => {
        console.log("View menu clicked!");
      },
      submenu: [
        { role: 'reload' }, 
        { role: 'togglefullscreen' },
        { type: 'separator' },
        {
          label: 'Show Console Log',
          accelerator: process.platform === 'darwin' ? 'Alt+Command+C' : 'Ctrl+Shift+C',
          click: () => {
            console.log("Show Console Log menu item clicked!");
            if (mainWindow) {
              // Open DevTools and focus on Console tab
              if (!mainWindow.webContents.isDevToolsOpened()) {
                mainWindow.webContents.openDevTools({ mode: 'detach' });
              }
              // Execute JavaScript to focus Console tab in DevTools
              mainWindow.webContents.executeJavaScript(`
                // Focus the console tab in DevTools (this runs in the renderer context)
                console.log('Console log viewer opened via menu');
              `);
              console.log("Console log viewer opened via View menu");
            }
          }
        }
      ],
    },
    {
      label: 'Help',
      submenu: [{ role: 'about' }],
    },
  ];
  return Menu.buildFromTemplate(template);
}

/**
 * Updates the application menu to reflect current state
 */
function updateMenu() {
  const menu = createMainMenu();
  Menu.setApplicationMenu(menu);
}

function createWindow() {
  console.log("Creating BrowserWindow...");
  mainWindow = new BrowserWindow({
    width: 1400,      // Increased width
    height: 900,      // Increased height
    frame: false,     // Borderless window
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Since __dirname points to dist/main after build,
  // our index.html is in dist/renderer. We set the path accordingly.
  const indexPath = path.join(__dirname, '../renderer/index.html');
  console.log("Attempting to load HTML from:", indexPath);

  mainWindow.loadFile(indexPath)
    .then(() => {
      console.log("HTML loaded successfully.");
      // Check the startup preference and open/close accordingly
      const shouldOpenOnStartup = getStartupPreference();
      if (shouldOpenOnStartup) {
        // Open DevTools in detached mode based on startup preference
        mainWindow?.webContents.openDevTools({ mode: 'detach' });
        console.log("DevTools opened based on startup preference.");
      } else {
        console.log("DevTools remains closed based on startup preference.");
      }
    })
    .catch((err) => {
      console.error("Error loading HTML:", err);
    });

  mainWindow.on('closed', () => {
    console.log("Main window closed.");
    mainWindow = null;
  });

  // Add event listeners for DevTools state changes
  mainWindow.webContents.on('devtools-opened', () => {
    console.log("DevTools opened externally, updating menu");
    updateMenu();
  });

  mainWindow.webContents.on('devtools-closed', () => {
    console.log("DevTools closed externally, updating menu");
    updateMenu();
  });

  const menu = createMainMenu();
  Menu.setApplicationMenu(menu);
  console.log("Main window menu created and set with DevTools options");
}

app.on('window-all-closed', () => {
  console.log("All windows closed. Exiting app.");
  app.quit();
});

// Clean up backend when app is quitting
app.on('will-quit', () => {
  if (isBackendManagedByUs()) {
    console.log("App quitting - stopping backend server we started...");
    stopBackend();
  }
});

// IPC handlers for window controls
ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-maximize', () => {
  if (!mainWindow) return;
  mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
});
ipcMain.on('window-close', () => mainWindow?.close());

// IPC handler for DevTools
ipcMain.on('open-devtools', () => {
  if (mainWindow && !mainWindow.webContents.isDevToolsOpened()) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
    console.log('[IPC] DevTools opened via renderer request');
  }
});

// IPC handler for folder selection dialog
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    title: 'Select USFM Bible Directory'
  });

  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }

  return result.filePaths[0];
});

app.on('activate', () => {
  if (mainWindow === null) {
    console.log("Recreating window on app activation.");
    createWindow();
  }
});

app.whenReady().then(async () => {
  console.log("App is ready. Ensuring backend is running...");

  const backendReady = await ensureBackendRunning();

  if (!backendReady) {
    console.error("Failed to start backend server. App may not function correctly.");
    // Continue anyway - user might start backend manually
  }

  console.log("Creating window...");
  createWindow();
});

