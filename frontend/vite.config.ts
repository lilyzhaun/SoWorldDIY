/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { resolve } from 'path'
import { copyFileSync, mkdirSync } from 'node:fs'

const appVersion = process.env.npm_package_version || new Date().toISOString().replace(/[-:.TZ]/g, '')
const srcDir = fileURLToPath(new URL('./src', import.meta.url))
const projectDir = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'distribute-licenses',
      apply: 'build',
      closeBundle() {
        mkdirSync('dist/licenses', { recursive: true })
        for (const name of ['react', 'react-dom', 'scheduler', 'dompurify']) {
          copyFileSync(`node_modules/${name}/LICENSE`, `dist/licenses/${name}.txt`)
        }
        copyFileSync('../LICENSE', 'dist/licenses/PROJECT-LICENSE.txt')
        copyFileSync('../THIRD_PARTY_NOTICES.md', 'dist/licenses/THIRD_PARTY_NOTICES.md')
      },
    },
  ],
  resolve: {
    alias: {
      '@': srcDir,
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  build: {
    rolldownOptions: {
      output: { comments: { legal: true } },
      input: {
        login: resolve(projectDir, 'login.html'),
        main: resolve(projectDir, 'index.html'),
      },
    },
  },
  test: {
    environment: 'happy-dom',
    include: ['tests/**/*.{test,spec}.{ts,tsx,mjs}', 'src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['tests/browser/**', 'node_modules/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'lcov'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.{test,spec}.{ts,tsx}', 'src/**/*.d.ts', 'src/main.tsx', 'src/login.tsx', '**/*.css'],
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
