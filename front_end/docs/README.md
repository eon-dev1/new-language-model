# NLM Front-End Documentation

## Overview

The NLM (New Language Model) front-end is an Electron desktop application built with React and TypeScript for managing biblical translation projects. It provides a modern, futuristic interface for creating and managing language projects with support for Bible reading, dictionary management, and translation memories.

## Setup

See the [repo root README](../../README.md) for full setup instructions (npm install, Python venv, MongoDB credentials, `npm run dev`).

## Production Build

```bash
cd front_end
npm run build
```

## Running Tests

```bash
cd front_end
npm test              # All tests (main + renderer, single run)
npm run test:main     # Main process tests only
npm run test:renderer # Renderer tests only
npm run test:coverage # With coverage report
```

## Technology Stack

| Technology | Purpose |
|------------|---------|
| Electron | Desktop application framework |
| React | UI component library |
| TypeScript | Type-safe JavaScript |
| Material-UI | Component library |
| Framer Motion | Animation library |
| Vite | Renderer process bundler |
| Webpack | Main process bundler |
| Vitest | Test framework |

## Project Structure

```
front_end/
├── src/
│   ├── main/                    # Electron main process
│   │   ├── main.ts              # Entry point, window management, IPC handlers
│   │   ├── preload.ts           # IPC security bridge (contextBridge)
│   │   ├── backend-manager.ts   # FastAPI subprocess management
│   │   ├── mongod-manager.ts    # MongoDB process management
│   │   ├── devtools-manager.ts  # DevTools state persistence
│   │   └── utils.ts             # Main process utilities
│   │
│   ├── renderer/                # React application
│   │   ├── index.tsx            # React root, theme/provider setup
│   │   ├── app.tsx              # Root component with TopBar and ChatDrawer
│   │   ├── Homepage.tsx         # Language project list, create project
│   │   ├── TopBar.tsx           # Custom frameless window title bar
│   │   ├── constants.ts         # Shared renderer constants
│   │   ├── api.ts               # Backend API communication
│   │   ├── types/               # TypeScript interfaces
│   │   │   └── LanguageProject.ts
│   │   ├── contexts/            # React contexts
│   │   │   ├── SettingsContext.tsx
│   │   │   └── ChatContext.tsx
│   │   ├── components/          # Renderer-scoped components
│   │   │   └── SettingsDialog.tsx
│   │   └── theme/
│   │       └── createDynamicTheme.ts
│   │
│   └── components/              # Feature components
│       ├── LanguageProject.tsx   # Project overview with resource navigation
│       ├── BibleReader.tsx       # Three-view Bible navigation
│       ├── DictionaryViewer.tsx  # Dictionary viewer and editor
│       ├── GrammarViewer.tsx     # Grammar category viewer
│       ├── MemoriesViewer.tsx    # Memories/notes viewer
│       ├── ChatDrawer.tsx        # AI chat side panel
│       ├── NewProjectDialog.tsx  # Project creation dialog
│       └── ...
│
├── tests/                       # Test files
│   ├── setup.ts                 # Test setup configuration
│   ├── devtools-manager.test.ts # DevTools state tests
│   ├── mongod-manager.test.ts   # MongoDB manager tests
│   └── renderer/                # Renderer process tests
│       ├── setup.ts
│       ├── SettingsContext.test.tsx
│       ├── createDynamicTheme.test.ts
│       ├── searchFilters.test.ts
│       └── ...
│
├── dist/                        # Compiled output (generated)
│   ├── main/                    # Compiled main process
│   └── renderer/                # Compiled React app
│
├── docs/                        # Documentation (this directory)
│
├── package.json                 # Dependencies and scripts
├── webpack.config.js            # Main process bundler config
├── vite.config.js               # Renderer process bundler config
├── vitest.config.ts             # Test framework config
├── tsconfig.json                # Root TypeScript config
├── tsconfig.main.json           # Main process TypeScript config
└── tsconfig.renderer.json       # Renderer process TypeScript config
```

## Key Concepts

### Resource Types

Each language project provides three resource views:
1. **Bible** - Scripture texts with book/chapter/verse navigation and verification
2. **Dictionary** - Word definitions with inline editing and human verification
3. **Memories** - Grammar categories, notes, and correction history

### Frameless Window

The application uses a custom frameless window design with:
- Static always-visible title bar at the top of the viewport
- Custom window controls (minimize, maximize, close)
- Draggable title bar region for window movement

## Documentation Index

- [Architecture](./architecture.md) - Electron process model, IPC communication, security
- [Components](./components.md) - React component documentation and usage
- [API Layer](./api-layer.md) - Backend communication
- [Development](./development.md) - Development setup, build process, testing
- [Types](./types.md) - TypeScript interfaces and data models

## Backend Integration

The front-end connects to the NLM FastAPI backend:

| Setting | Value |
|---------|-------|
| Endpoint | `http://127.0.0.1:8221/api` |
| Authentication | None (localhost-only binding) |
| Configuration | Hardcoded in `src/renderer/api.ts` |

See [API Layer](./api-layer.md) for detailed communication patterns.

## Security Model

- **Context Isolation**: Renderer process cannot access Node.js directly
- **IPC Bridge**: Controlled API exposed via `contextBridge`
- **Localhost-Only**: Backend binds to 127.0.0.1; no external network access

See [Architecture](./architecture.md) for detailed security information.
