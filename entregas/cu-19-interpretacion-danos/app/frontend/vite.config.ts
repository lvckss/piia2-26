import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { tanstackRouter } from '@tanstack/router-plugin/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
    }),
    tailwindcss(),
    react(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
      "@server": path.resolve(import.meta.dirname, "../server")
    }
  },
  server: {
    proxy: {
      "/api": {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true,
      },
      '/dataset': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
    }
  }
})
