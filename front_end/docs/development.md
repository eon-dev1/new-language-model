# Development Guide

This document covers the development workflow, build process, testing, and debugging for the NLM front-end application.

## Prerequisites

- **Node.js**: v18 or later (LTS recommended)
- **npm**: v9 or later
- **Git**: For version control
- **Backend Server**: FastAPI backend running on port 8221

## Initial Setup

### 1. Install Dependencies

```bash
cd front_end
npm install
```

### 2. Configure Environment

Create a `.env` file in the `front_end/` directory:

```env
VITE_API_BASE_URL=http://localhost:8221/api
```

### 3. Verify Backend

Ensure the FastAPI backend is running:

```bash
cd ../back_end
python main.py
```

## Development Workflow

### Starting Development Mode

```bash
npm run dev
```

This runs three processes concurrently (named `main`, `renderer`, `electron`):
1. **Webpack** (`dev:main`): Watches and rebuilds main process with `--mode development --watch`
2. **Vite** (`dev:renderer`): Serves renderer with hot module replacement
3. **Electron**: Launches application after main process builds

> **Note**: A `predev` hook (`node scripts/download-mongo-binaries.js`) runs automatically before the three concurrent processes to download/verify the embedded MongoDB binary.

### Development Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Start full development environment |
| `npm run dev:main` | Watch main process only |
| `npm run dev:renderer` | Start Vite dev server only |
| `npm start` | Run built application (no hot reload) |

### File Watching

- **Main process changes** (`src/main/`): Webpack rebuilds, requires app restart
- **Renderer changes** (`src/renderer/`): Vite hot reloads, no restart needed
- **Component changes** (`src/components/`): Vite hot reloads

## Build Process

### Full Build

```bash
npm run build
```

Builds both processes sequentially:
1. Main process via Webpack
2. Renderer process via Vite

### Individual Builds

```bash
npm run build:main      # Webpack production build
npm run build:renderer  # Vite production build
```

### Build Output

```
dist/
├── main/
│   ├── main.js         # Electron main process
│   └── preload.js      # Preload script
│
└── renderer/
    ├── index.html      # Entry HTML
    ├── assets/         # JS, CSS, fonts
    └── ...
```

### Running Production Build

```bash
npm start
# or
electron dist/main/main.js
```

## TypeScript Configuration

The project uses separate TypeScript configurations:

### tsconfig.json (Root)

Configures project references:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.main.json" },
    { "path": "./tsconfig.renderer.json" }
  ]
}
```

### tsconfig.main.json

Main process configuration:
- Target: ES2020
- Module: CommonJS
- Types: Node.js
- Strict mode enabled

### tsconfig.renderer.json

Renderer process configuration:
- Target: ES2020
- Module: ESNext
- JSX: react-jsx
- Types: DOM
- Strict mode enabled

## Testing

### Test Framework

The project uses **Vitest** with two separate configurations:
- **Main process**: Node.js environment for testing Electron main process code
- **Renderer process**: jsdom environment for React component testing

### Running Tests

```bash
npm test              # All tests (main + renderer, single run)
npm run test:main     # Main process tests only
npm run test:renderer # Renderer tests only
npm run test:coverage # With coverage report
```

### Test Configurations

**vitest.config.ts** (Main Process):

```typescript
export default defineConfig({
  test: {
    environment: 'node',
    globals: true,
    include: ['tests/**/*.test.ts', 'src/**/*.test.ts'],
    testTimeout: 10000,
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/main/**/*.ts'],
      exclude: ['src/main/**/*.test.ts'],
      reporter: ['text', 'html', 'lcov'],
    },
  },
});
```

**vitest.renderer.config.ts** (Renderer Process):

```typescript
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',       // Browser DOM simulation
    globals: true,
    include: ['tests/renderer/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests/renderer/setup.ts'],
    testTimeout: 10000,
    coverage: {
      provider: 'v8',
      include: ['src/renderer/**/*.{ts,tsx}'],
      exclude: ['src/renderer/**/*.test.{ts,tsx}'],
      reporter: ['text', 'html', 'lcov'],
    },
  },
});
```

### Test Files

```
tests/
├── setup.ts                        # Main process test setup/mocks
├── devtools-manager.test.ts        # DevTools state tests
├── mongod-manager.test.ts          # MongoDB manager tests
│
└── renderer/
    ├── setup.ts                    # Renderer test setup (jsdom config)
    ├── SettingsContext.test.tsx    # Settings context tests
    ├── SettingsDialog.test.tsx     # Settings dialog tests
    ├── createDynamicTheme.test.ts  # Theme factory tests
    ├── searchFilters.test.ts       # Search filter function tests
    ├── streamChatBody.test.ts      # Chat body streaming tests
    ├── ChatModes.test.tsx          # Chat mode tests
    └── integration.test.tsx        # Integration tests
```

### Writing Tests

**Main process test example**:
```typescript
import { describe, it, expect, vi } from 'vitest';
import { DevToolsManager } from '../src/main/devtools-manager';

describe('DevToolsManager', () => {
  it('should track open state', () => {
    const manager = new DevToolsManager();
    manager.setOpen(true);
    expect(manager.isOpen()).toBe(true);
  });
});
```

**Renderer test example**:
```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SettingsProvider, useSettings } from '../../src/renderer/contexts/SettingsContext';

describe('SettingsContext', () => {
  it('should provide default settings', () => {
    const TestComponent = () => {
      const { settings } = useSettings();
      return <div>{settings.fontSize}</div>;
    };

    render(
      <SettingsProvider>
        <TestComponent />
      </SettingsProvider>
    );
    expect(screen.getByText('16')).toBeDefined();
  });
});
```

### Coverage Report

Coverage reports are generated in:
- Console output (text)
- `coverage/` directory (HTML, LCOV)

## Code Quality

### ESLint

```bash
npm run lint
```

Configuration extends TypeScript ESLint rules.

### Prettier

```bash
npm run format
```

Formats all files in the project.

### Pre-Commit Checks

Consider adding to your workflow:

```bash
npm run lint && npm test && npm run build
```

## Debugging

### DevTools Access

1. **Menu**: View > Show Console Log (Ctrl+Shift+C / Alt+Cmd+C)
2. **TopBar**: View submenu > Show Console Log
3. **Programmatic**: `window.api.openDevTools()`

### Console Logging

The application uses prefixed logging:

| Prefix | Source |
|--------|--------|
| `[App]` | App component |
| `[TopBar]` | TopBar component |
| `[API]` | API layer |
| `[Main]` | Main process IPC |
| `[NewProjectDialog]` | Project creation dialog |
| `[Homepage]` | Homepage component |

### Common Debug Scenarios

**IPC Issues**:
```javascript
// In DevTools console
window.api  // Should show available functions
await window.api.selectFolder()  // Test folder selection
```

**API Connection**:
```javascript
// In DevTools console
import { testApiConnection } from './api';
await testApiConnection();
```

### DevTools State Persistence

DevTools state is persisted between sessions:
- Opens automatically if it was open when app closed
- Controlled by `devtools-manager.ts`

## Webpack Configuration

### Main Process (webpack.config.js)

```javascript
module.exports = {
  mode: 'development',  // or 'production' for build
  entry: {
    main: './src/main/main.ts',
    preload: './src/main/preload.ts',
  },
  target: 'electron-main',
  output: {
    path: path.resolve(__dirname, 'dist/main'),
    filename: '[name].js',
  },
  module: {
    rules: [{
      test: /\.ts$/,
      use: {
        loader: 'ts-loader',
        options: { configFile: 'tsconfig.main.json' }
      },
    }],
  },
  node: {
    __dirname: false,
    __filename: false,
  },
};
```

Key settings:
- `target: 'electron-main'`: Enables Node.js modules
- `__dirname: false`: Preserves runtime __dirname

## Vite Configuration

### Renderer Process (vite.config.js)

```javascript
export default defineConfig({
  plugins: [react()],
  root: 'src/renderer',
  envDir: path.resolve(__dirname),
  build: {
    outDir: '../../dist/renderer',
    emptyOutDir: true,
  },
  base: './',
});
```

Key settings:
- `root: 'src/renderer'`: Source directory
- `envDir`: Loads `.env` from project root
- `base: './'`: Relative paths for Electron file:// protocol

## Common Issues

### "VITE_API_BASE_URL is not defined"

Create `.env` file:
```env
VITE_API_BASE_URL=http://localhost:8221/api
```

### Main Process Changes Not Reflected

Webpack watch may not trigger Electron restart. Manually restart:
```bash
# Kill existing electron process
# Run npm run dev again
```

### Hot Reload Not Working

Check Vite dev server is running:
```bash
npm run dev:renderer
# Should show "Local: http://localhost:5173/"
```

### TypeScript Errors

Ensure correct config is used:
```bash
# Check for type errors
npx tsc -p tsconfig.main.json --noEmit
npx tsc -p tsconfig.renderer.json --noEmit
```

### Tests Failing with Timeouts

Increase timeout in vitest.config.ts:
```typescript
testTimeout: 20000,  // 20 seconds
```

## Project Scripts Reference

| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `concurrently ...` | Full dev environment |
| `dev:main` | `webpack --mode development --watch` | Watch main process |
| `dev:renderer` | `vite` | Vite dev server |
| `build` | `build:main && build:renderer` | Full production build |
| `build:main` | `webpack --mode production` | Build main process |
| `build:renderer` | `vite build` | Build renderer |
| `start` | `electron dist/main/main.js` | Run built app |
| `test` | `vitest run` (both suites) | All tests, single run |
| `test:main` | `vitest` | Main process tests |
| `test:renderer` | `vitest --config ...` | Renderer tests |
| `test:coverage` | `vitest run --coverage` | Tests with coverage |
| `lint` | `eslint . --ext .ts,.tsx` | Run ESLint |
| `format` | `prettier --write .` | Format code |

## Development Tips

### Fast Iteration

1. Use `npm run dev` for hot reload
2. Keep DevTools open for immediate feedback
3. Watch console for prefixed logs

### Component Development

1. Start with renderer-only changes (hot reload)
2. Test in isolation before integration
3. Use TypeScript for early error detection

### Testing Strategy

1. Test main process logic in isolation
2. Mock IPC for renderer testing
3. Use integration tests for API layer

### Performance

1. Use React DevTools for component profiling
2. Check bundle size with `npm run build`
3. Monitor memory in Electron DevTools
