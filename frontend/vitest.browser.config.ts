import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    testTimeout: 25_000,
    hookTimeout: 25_000,
    maxWorkers: 1,
    include: ['tests/browser/**/*.browser.test.mjs'],
    exclude: ['node_modules/**'],
  },
})
