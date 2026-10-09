import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the Vite server proxies /api to FastAPI so the browser sees a
// single origin: session cookies stay first-party and no CORS is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 4000, // Monaco is large by nature
  },
})
