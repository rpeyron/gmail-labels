import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  // relative base: assets resolve under GitHub Pages sub-path (e.g. /gmail-labels/)
  base: './',
  plugins: [react()],
});
