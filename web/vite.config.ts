import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const BACKEND_HOST = process.env.VITE_BACKEND_HOST || '127.0.0.1';
const BACKEND_PORT = process.env.VITE_BACKEND_PORT || '8000';
const BACKEND_ORIGIN = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const BACKEND_WS_ORIGIN = `ws://${BACKEND_HOST}:${BACKEND_PORT}`;

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: BACKEND_ORIGIN,
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/ws': {
        target: BACKEND_WS_ORIGIN,
        changeOrigin: true,
        ws: true,
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  }
})
