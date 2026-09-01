# Development Guide

Front-end-specific dev setup, scripts, and testing. For npm install / Python venv / MongoDB credentials shared with the rest of the app, see the [repo root README](../../README.md).

## Prerequisites

- Node.js and npm (a current LTS Node works; no `engines` field in `package.json` pins a minimum version)
- Backend virtual environment set up per the root README (`back_end/nlm_backend_venv`)

## Environment Setup

No `.env` file is required — the API base URL is hardcoded in `src/renderer/api.ts` as `http://127.0.0.1:8221/api`. To point at a different backend, edit that constant directly.

```bash
npm run dev
```

This runs webpack (main process, watch mode), Vite (renderer dev server), and Electron concurrently. A `predev` hook downloads/verifies the embedded MongoDB binary before they start.

On launch, Electron's main process (`main.ts`) starts the embedded `mongod`, then the FastAPI backend subprocess, then creates the window — see [Architecture](./architecture.md) for the full process model and why that order matters.

## Project Scripts Reference

| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `concurrently ...` (main + renderer + electron) | Full dev environment |
| `dev:main` | `webpack --mode development --watch` | Watch main process only |
| `dev:renderer` | `vite` | Vite dev server only |
| `build` | `build:main && build:renderer` | Full production build |
| `build:main` | `webpack --mode production` | Build main process |
| `build:renderer` | `vite build` | Build renderer |
| `start` | `electron dist/main/main.js` | Run built app |
| `prepare:mongo` | `node scripts/download-mongo-binaries.js` | Download/verify the embedded MongoDB binary (also runs automatically via `predev`) |
| `test` | `vitest run && vitest run --config vitest.renderer.config.ts` | All tests (main + renderer), single run |
| `test:main` | `vitest --config vitest.config.ts` | Main process tests |
| `test:renderer` | `vitest --config vitest.renderer.config.ts` | Renderer tests |
| `test:coverage` | `vitest run --coverage && vitest run --config vitest.renderer.config.ts --coverage` | Tests with coverage |
| `lint` | `eslint . --ext .ts,.tsx` | No ESLint config currently exists in `front_end`, so this fails until one is added |
| `format` | `prettier --write .` | Formats on Prettier's defaults — no config file needed |
