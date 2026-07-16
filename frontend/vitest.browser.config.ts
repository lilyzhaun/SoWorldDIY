import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/browser/**/*.browser.test.mjs'],
    exclude: ['node_modules/**'],
  },
})
