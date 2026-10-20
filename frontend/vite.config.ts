import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  build: {
    outDir: path.resolve(import.meta.dirname, '../src/whoop_mcp/static'),
    emptyOutDir: true,
    chunkSizeWarningLimit: 800,
  },
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
})
