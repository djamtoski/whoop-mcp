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
    // WHOOP_API points the dev server at another dashboard, e.g. the preview copy on :8001.
    proxy: { '/api': process.env.WHOOP_API ?? 'http://localhost:8000' },
  },
})
