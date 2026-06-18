import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react()
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 8081,
    host: "0.0.0.0",
    proxy: {
      '/api/v1': {
        target: 'http://8.130.172.227:8000',
        changeOrigin: true,
      }
    }
  }
})
