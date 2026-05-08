// main.ts
import { closeLog } from './logger';

import { app, BrowserWindow, Menu, MenuItemConstructorOptions, ipcMain, dialog, shell } from 'electron';
import * as path from 'path';
import { getStartupPreference } from './devtools-manager';
import { ensureBackendRunning, stopBackend, isBackendManagedByUs } from './backend-manager';
import { ensureMongodRunning, stopMongod } from './mongod-manager';

// Initialize DevTools manager and get saved state
// We'll pass the mainWindow after it's created

let mainWindow: BrowserWindow | null = null;

/**
 * Creates the application main menu
 * @returns The built menu from template
 */
function createMainMenu() {
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
      submenu: [
        { role: 'reload' },
        { role: 'togglefullscreen' },
        { type: 'separator' },
        { role: 'toggleDevTools' },
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

  mainWindow.maximize();

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

  mainWindow.webContents.on('context-menu', (_e, params) => {
    const items: MenuItemConstructorOptions[] = [];

    if (params.isEditable) {
      if (params.editFlags.canCut)       items.push({ label: 'Cut',        role: 'cut' });
      if (params.editFlags.canCopy)      items.push({ label: 'Copy',       role: 'copy' });
      if (params.editFlags.canPaste)     items.push({ label: 'Paste',      role: 'paste' });
      if (params.editFlags.canSelectAll) items.push({ label: 'Select All', role: 'selectAll' });
    } else if (params.selectionText) {
      items.push({ label: 'Copy', role: 'copy' });
    }

    if (items.length > 0) {
      Menu.buildFromTemplate(items).popup();
    }
  });

  const menu = createMainMenu();
  Menu.setApplicationMenu(menu);
  console.log("Main window menu created and set with DevTools options");
}

app.on('window-all-closed', () => {
  console.log("All windows closed. Exiting app.");
  app.quit();
});

// Clean up backend and mongod when app is quitting
app.on('will-quit', () => {
  if (isBackendManagedByUs()) {
    console.log("App quitting - stopping backend server we started...");
    stopBackend();  // backend first (holds DB connections)
  }
  stopMongod();   // then mongod (no-op if not managed by us)
  closeLog();     // flush and close log stream last
});

// IPC handlers for window controls
ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-maximize', () => {
  if (!mainWindow) return;
  mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
});
ipcMain.on('window-close', () => mainWindow?.close());

// IPC handler for opening external URLs in the system browser
ipcMain.handle('open-external', (_event, url: string) => {
  if (typeof url !== 'string') return;
  try {
    if (new URL(url).protocol !== 'https:') return;
  } catch {
    return;
  }
  return shell.openExternal(url);
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
  console.log("App is ready. Starting bundled mongod...");

  const mongodReady = await ensureMongodRunning();
  if (!mongodReady) {
    console.warn("Bundled mongod could not start.");
    const { response } = await dialog.showMessageBox({
      type: 'warning',
      title: 'Database Unavailable',
      message: 'The bundled database could not be started.',
      detail: 'Try re-installing the application if the problem persists.',
      buttons: ['Quit', 'Continue Anyway'],
      defaultId: 0,
    });
    if (response === 0) {
      app.quit();
      return;
    }
  }

  console.log("Ensuring backend is running...");

  const backendReady = await ensureBackendRunning();
  if (!backendReady) {
    console.error("Failed to start backend server after 30 attempts.");
    await dialog.showMessageBox({
      type: 'error',
      title: 'Backend Failed to Start',
      message: 'The NLM backend server could not be started.',
      detail: 'Check that Python and the virtual environment are correctly installed in nlm_backend_venv.',
      buttons: ['Quit'],
      defaultId: 0,
    });
    app.quit();
    return;
  }

  console.log("Creating window...");
  createWindow();
});

