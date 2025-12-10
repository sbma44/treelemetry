import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  base: '/',
  build: {
    outDir: '../docs',
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    open: true,
  },
});

