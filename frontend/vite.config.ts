/// <reference types="vitest/config" />
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
    },
  },
  test: {
    environment: 'happy-dom',
    include: [
      'tests/**/*.{test,spec}.{ts,tsx}',
      'src/**/*.{test,spec}.{ts,tsx}',
    ],
    exclude: [
      'tests/browser/**',
      'node_modules/**',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'lcov'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.{test,spec}.{ts,tsx}',
        'src/**/*.d.ts',
        'src/main.tsx',
        'src/login.tsx',
        '**/*.css',
      ],
      // Floor of measured post-task-13 coverage (line/branch already >=70).
      thresholds: {
        lines: 83,
        branches: 70,
        functions: 67,
        statements: 79,
      },
    },
  },
})
