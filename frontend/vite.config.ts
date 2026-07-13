import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { resolve } from 'path'

const appVersion = process.env.npm_package_version || new Date().toISOString().replace(/[-:.TZ]/g, '')
const srcDir = fileURLToPath(new URL('./src', import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': srcDir,
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  build: {
    rollupOptions: {
      input: {
        login: resolve(__dirname, 'login.html'),
        main: resolve(__dirname, 'index.html'),
      },
    }
  },
})
