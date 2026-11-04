import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Built into ../web/app and served by app.py at /app/ (offline, no CDN).
// `npm run dev` proxies the API and scene files to the Python server on :8000.
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  build: { outDir: '../web/app', emptyOutDir: true, chunkSizeWarningLimit: 1200 },
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000', '/results': 'http://127.0.0.1:8000' },
  },
});
