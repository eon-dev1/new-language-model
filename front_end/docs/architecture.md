# Architecture

This document describes the NLM front-end's Electron process model, IPC design, and security rationale.

## Process Model

The application follows Electron's dual-process architecture:

```
┌───────────────────────────────────────────────────────────────────┐
│                          Main Process                              │
│  (Node.js runtime — full system access)                            │
│                                                                     │
│  main.ts              window creation, app menu, IPC handlers      │
│  backend-manager.ts   start/stop the FastAPI backend subprocess    │
│  mongod-manager.ts    start/stop the embedded MongoDB process      │
│  devtools-manager.ts  startup DevTools preference only —           │
│                        no cross-session persistence                │
│  logger.ts            intercepts console.*, writes rotating,       │
│                        timestamped log files (imported first)      │
│                                                                     │
│  IPC Handlers: window-minimize | window-maximize | window-close    │
│                open-external   | select-folder                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ preload.ts (contextBridge)
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                        Renderer Process                              │
│  (Chromium browser context — sandboxed)                             │
│                                                                       │
│  window.api: minimize() | maximize() | close()                      │
│              | selectFolder() | openExternal()                      │
│                                                                       │
│  index.tsx → App → Homepage → LanguageProject                       │
│                 ↘                 ↘                                  │
│                  TopBar            Viewer (Bible/Dict/Memories)      │
│                  ChatDrawer                                          │
└────────────────────────────────────────────────────────────────────┘
```

This IPC bridge only carries window controls, folder selection, and external-URL opening. It is **not** how the app talks to its own backend — see below.

## Data Flow: Renderer ↔ Backend

The renderer's `api.ts` calls the FastAPI backend directly over HTTP, completely independent of the IPC bridge and the Main process:

```
Renderer (api.ts)  ──fetch()──▶  http://127.0.0.1:8221/api  ──▶  FastAPI backend
```

`backend-manager.ts` (Main process) only starts and stops that backend subprocess at app launch/quit — once it's running, every request bypasses Main entirely. This direct HTTP path is the app's primary data flow; IPC is reserved for the handful of Electron-native operations listed above.

## Main Process (`src/main/`)

Startup order in `main.ts` (`app.whenReady()`): start the embedded mongod → start the FastAPI backend subprocess → create the window. Either of the first two failing aborts startup with a dialog.

### main.ts

- **BrowserWindow creation**: frameless, context-isolated, starts at 1400×900 but is immediately maximized on launch (`mainWindow.maximize()`) — the initial dimensions are never actually visible.
- **Application menu**: File / Edit / View / Help, built from Electron's built-in roles (`toggleDevTools` lives under View — there's no custom DevTools toggle).
- **Right-click context menu**: Cut/Copy/Paste/Select All on editable fields, Copy on selected text — wired directly on `webContents`, separate from the application menu.
- **IPC handlers**: window controls, folder selection, external-URL opening (validated to `https://` only).
- **Shutdown** (`will-quit`): stops the backend (if we started it), then mongod, then flushes the log file — in that order, since the backend holds the DB connections.

```typescript
mainWindow = new BrowserWindow({
  width: 1400,
  height: 900,
  frame: false,  // Frameless for custom title bar
  webPreferences: {
    preload: path.join(__dirname, 'preload.js'),
    nodeIntegration: false,   // Security: no Node in renderer
    contextIsolation: true,   // Security: isolated contexts
  },
});
```

### backend-manager.ts

Starts/stops the FastAPI backend subprocess (Python, via the `nlm_backend_venv` virtualenv) and polls `/api/check-connection` until it responds before considering it ready. Only manages the process lifecycle — see Data Flow above for how the renderer actually talks to it.

### mongod-manager.ts

Starts/stops the embedded MongoDB process before the backend needs it. Uses a TCP port check (27019) to detect an already-running instance and avoid double-spawning, and clears a stale `WiredTiger.lock` left behind by an unclean shutdown.

### devtools-manager.ts

DevTools auto-opens only when the app is running unpacked (`!app.isPackaged`) — a static constant, not something restored from a previous session. The module also exports toggle/state-tracking functions, but production code doesn't call them; the actual DevTools toggle is Electron's built-in `toggleDevTools` menu role.

### logger.ts

Imported first in `main.ts`. Intercepts `console.log/warn/error` and mirrors every call into a timestamped, rotating log file (most recent 10 kept), in addition to the normal console output.

### preload.ts

The security bridge between main and renderer processes. Uses `contextBridge` to expose a controlled API:

```typescript
contextBridge.exposeInMainWorld('api', {
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),

  // Folder selection for imports (invoke = async with return value)
  selectFolder: () => ipcRenderer.invoke('select-folder'),

  // Open external URLs in the system browser (main process enforces https:// only)
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
});
```

## IPC Communication Patterns

**One-way (fire and forget)** — used for window controls:

```typescript
// Renderer → Main, no response expected
window.api.minimize();
```
```typescript
// Main process handler
ipcMain.on('window-minimize', () => mainWindow?.minimize());
```

**Two-way (request/response)** — used for folder selection and external URLs:

```typescript
// Renderer → Main, awaits response
const folderPath = await window.api.selectFolder();  // string | null
```
```typescript
// Main process handler
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog({ properties: ['openDirectory'] });
  return result.canceled ? null : result.filePaths[0];
});
```

## Security Model

### Context Isolation

The renderer process cannot access Node.js APIs directly. All communication with the main process goes through the preload script's controlled interface.

```typescript
webPreferences: {
  nodeIntegration: false,   // No require() in renderer
  contextIsolation: true,   // Separate JavaScript contexts
}
```

### Localhost-Only Backend

The FastAPI backend binds to `127.0.0.1` only — no external network access, and no credentials are transmitted between the renderer and the backend. Authentication is deliberately disabled: this is a local-only desktop app, and MongoDB provides its own authentication layer for database access. This is the single canonical statement of that rationale — other docs link here rather than restating it.

### IPC Security

The preload script only exposes specific, validated functions: no arbitrary code execution, no direct file system access from the renderer, no access to Electron internals.

## UI: Frameless Window

The application uses a custom frameless window with:
- `-webkit-app-region: drag` on the AppBar for window movement
- `-webkit-app-region: no-drag` on interactive elements (buttons)
- Custom minimize/maximize/close buttons in `TopBar`

## Error Handling

See [API Layer — Error Handling](./api-layer.md#error-handling) for how `api.ts` surfaces backend errors (the `ApiError` class and its `.status`/`.body` contract) — not repeated here.
