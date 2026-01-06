// vite.config.js

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  root: 'src/renderer',
  envDir: path.resolve(__dirname), // instructs Vite to load .env from the project root
  build: {
    outDir: '../../dist/renderer',
    emptyOutDir: true,
  },
  base: './',
});