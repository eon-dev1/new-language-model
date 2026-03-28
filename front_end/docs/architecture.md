# Architecture

This document describes the NLM front-end architecture, including the Electron process model, inter-process communication (IPC), and security model.

## Process Model

The application follows Electron's dual-process architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Main Process                              │
│  (Node.js runtime - full system access)                         │
│                                                                  │
│  ┌─────────────┐  ┌──────────────────┐  ┌───────────────────┐   │
│  │   main.ts   │  │ backend-manager  │  │ devtools-manager  │   │
│  │             │  │                  │  │                   │   │
│  │ - Window    │  │ - Start/stop     │  │ - State persist   │   │
│  │ - IPC       │  │   FastAPI        │  │ - Toggle DevTools │   │
│  │ - Menu      │  │   subprocess     │  │                   │   │
│  └─────────────┘  └──────────────────┘  └───────────────────┘   │
│                                                                  │
│                     IPC Handlers                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ window-minimize | window-maximize | window-close          │ │
│  │ open-devtools   | select-folder                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                         preload.ts
                     (contextBridge)
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                       Renderer Process                           │
│  (Chromium browser context - sandboxed)                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    window.api                                ││
│  │  minimize() | maximize() | close() | openDevTools()         ││
│  │  selectFolder()                                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                   React Application                          ││
│  │                                                              ││
│  │   index.tsx → App → Homepage → LanguageProject               ││
│  │                  ↘                 ↘                         ││
│  │                   TopBar            Viewer (Bible/Dict/...)   ││
│  │                   ChatDrawer                                  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Main Process (`src/main/`)

The main process is the application's entry point and has full access to Node.js APIs and the operating system.

### main.ts

Entry point that handles:
- **BrowserWindow Creation**: Frameless window (1400x900) with context isolation enabled
- **Application Menu**: File, Edit, View, Help menus with DevTools access
- **IPC Handlers**: Window controls and folder selection
- **DevTools Management**: State persistence across sessions

```typescript
// Window configuration
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

Starts and stops the FastAPI backend subprocess. Imported by `main.ts` and called during application startup/shutdown. Manages the Python process lifecycle so the backend is always available when the app is running.

### mongod-manager.ts

Manages the embedded MongoDB process lifecycle — starting the database before the backend needs it and cleaning up on exit.

### devtools-manager.ts

Persists DevTools state between sessions:
- Tracks whether DevTools was open when app closed
- Restores DevTools state on next startup
- Provides toggle functionality for menu integration

### preload.ts

The security bridge between main and renderer processes. Uses `contextBridge` to expose a controlled API:

```typescript
contextBridge.exposeInMainWorld('api', {
  // Window control functions
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),

  // DevTools functions
  openDevTools: () => ipcRenderer.send('open-devtools'),

  // Folder selection for imports (invoke = async with return value)
  selectFolder: () => ipcRenderer.invoke('select-folder'),
});
```

## Renderer Process (`src/renderer/`)

The renderer process runs in a Chromium browser context with limited capabilities for security.

### Entry Point (index.tsx)

Initializes the React application with a provider stack:

```typescript
// Provider nesting (outermost to innermost):
<SettingsProvider>        // User preferences (fontFamily, fontSize, etc.)
  <ThemedApp>             // Creates MUI theme from current settings
    <ChatProvider>        // Chat drawer state
      <App />
    </ChatProvider>
  </ThemedApp>
</SettingsProvider>
```

`ThemedApp` is a wrapper component inside `SettingsProvider` that consumes `useSettings()` to build a dynamic MUI theme, then wraps its children in `ThemeProvider` and `CssBaseline`.

### Component Hierarchy

```
App
 ├── Box (content area, width adjusts when chat opens)
 │    ├── TopBar (always visible)
 │    └── Homepage
 │         └── LanguageProject (when project selected)
 │              ├── BibleReader (when Bible selected)
 │              ├── DictionaryViewer (when Dictionary selected)
 │              └── MemoriesViewer (when Memories selected)
 └── ChatDrawer (side panel, outside content Box)
```

### State Management

The application uses a hybrid approach:
- **Component-level state**: `useState` hooks for local UI state
- **Context-based state**: `SettingsContext` for app-wide settings with localStorage persistence
- **Context-based state**: `ChatContext` for chat drawer open/close and width

Navigation is handled through:
- Callback functions passed as props (`onBack`, `onSelect`)
- Conditional rendering based on component state
- No React Router - single-page component-based navigation

#### SettingsContext

**Location**: `src/renderer/contexts/SettingsContext.tsx`

Provides app-wide settings state with automatic localStorage persistence.

```typescript
interface SettingsContextType {
  settings: AppSettings;
  updateSettings: (partial: Partial<AppSettings>) => void;
  resetSettings: () => void;
}

interface AppSettings {
  fontFamily: 'system-ui' | 'Times New Roman';
  fontSize: number;  // 12-24
  toolPreviewEnabled: boolean;
}
```

**Hook Usage**:
```typescript
const { settings, updateSettings, resetSettings } = useSettings();

// Update font size
updateSettings({ fontSize: 18 });

// Reset to defaults
resetSettings();
```

**localStorage Behavior**:
- Key: `nlm-app-settings`
- Automatically loads on mount
- Automatically saves on updates
- Falls back to defaults if corrupted

## IPC Communication Patterns

### One-Way Messages (Fire and Forget)

Used for window controls:

```typescript
// Renderer → Main (no response expected)
window.api.minimize();
window.api.maximize();
window.api.close();
window.api.openDevTools();
```

```typescript
// Main process handler
ipcMain.on('window-minimize', () => mainWindow?.minimize());
```

### Two-Way Messages (Request/Response)

Used for folder selection:

```typescript
// Renderer → Main (awaits response)
const folderPath = await window.api.selectFolder();
// folderPath: string | null
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

The FastAPI backend binds to `127.0.0.1` only. No credentials are transmitted between the renderer and the backend — authentication is disabled for local development.

### IPC Security

The preload script only exposes specific, validated functions:
- No arbitrary code execution
- No direct file system access from renderer
- No access to Electron internals

## Build System

### Dual Bundler Architecture

| Process | Bundler | Config | Output |
|---------|---------|--------|--------|
| Main | Webpack | webpack.config.js | dist/main/ |
| Renderer | Vite | vite.config.js | dist/renderer/ |

### TypeScript Configuration

Separate TypeScript configs for each process:

```
tsconfig.json              # Root project references
  ├── tsconfig.main.json   # Main process (Node.js types)
  └── tsconfig.renderer.json # Renderer (DOM types, React)
```

### Development Flow

```
npm run dev
    │
    ├─→ npm run dev:main     (Webpack --watch)
    │       └─→ Rebuilds src/main/ on changes
    │
    ├─→ npm run dev:renderer (Vite dev server)
    │       └─→ Hot module replacement for React
    │
    └─→ electron dist/main/main.js
            └─→ Starts after main process builds
```

## UI/UX Architecture

### Frameless Window Design

The application uses a custom frameless window with:
- `-webkit-app-region: drag` on the AppBar for window movement
- `-webkit-app-region: no-drag` on interactive elements (buttons)
- Custom minimize/maximize/close buttons in `TopBar`

### Static TopBar

`TopBar` is a `React.FC` that renders unconditionally — it is always visible at the top of the viewport. There is no mouse-triggered visibility logic.

### Theme System

The application uses a dynamic theme system that responds to user font settings.

#### createDynamicTheme

**Location**: `src/renderer/theme/createDynamicTheme.ts`

Factory function that creates MUI themes based on user settings.

```typescript
import { createDynamicTheme, AppSettings, DEFAULT_SETTINGS } from './theme/createDynamicTheme';

// Create theme with user settings
const theme = createDynamicTheme(settings);
```

**AppSettings Interface**:
```typescript
interface AppSettings {
  fontFamily: 'system-ui' | 'Times New Roman';
  fontSize: number;  // 12-24
  toolPreviewEnabled: boolean;
}

const DEFAULT_SETTINGS: AppSettings = {
  fontFamily: 'system-ui',
  fontSize: 16,
  toolPreviewEnabled: true,
};
```

**Font Stacks**:
```typescript
// system-ui
'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'

// Times New Roman
'"Times New Roman", Times, Georgia, serif'
```

**Dynamic Scaling**:
The theme scales all typography based on the font size setting:
```typescript
const scale = settings.fontSize / 16;  // 16px baseline
// h1: 3 * scale rem
// h2: 2 * scale rem
// body1: 1 * scale rem
// etc.
```

#### Base Theme Options

The dynamic theme preserves these non-typography settings:

```typescript
{
  palette: {
    mode: 'dark',
    background: {
      default: '#000000',  // True black
      paper: '#222222',    // Dark gray
    },
    primary: {
      main: '#C0C0C0',     // Silver
      dark: '#A0A0A0',
    },
    text: {
      primary: '#FFFFFF',
      secondary: '#CCCCCC',
    },
  },
  components: {
    MuiButton: { /* glowing hover effects */ },
    MuiPaper: { /* gradient backgrounds */ },
  },
}
```

#### Theme Integration

The theme is connected to SettingsContext via `ThemedApp` for automatic updates:

```typescript
// In index.tsx
function ThemedApp({ children }) {
  const { settings } = useSettings();
  const theme = useMemo(() => createDynamicTheme(settings), [settings]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}
```

## Error Handling

### API Communication

The `api.ts` module implements comprehensive error handling:
1. Response structure validation
2. JSON parse error handling
3. HTTP error status propagation
4. Detailed console logging for debugging
