import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { URL, fileURLToPath } from 'node:url'

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { createServer } from 'vite'

import { dumpBrowserDom, resolveBrowserExecutable } from './browserHarness.mjs'

const frontendRoot = fileURLToPath(new URL('../..', import.meta.url))
let server
let browserProfile
let browserExecutable
let testUrl

beforeAll(async () => {
  browserExecutable = await resolveBrowserExecutable()
  browserProfile = await mkdtemp(join(tmpdir(), '3hk-cmn-hook-browser-'))
  server = await createServer({ root: frontendRoot, logLevel: 'silent', server: { host: '127.0.0.1' } })
  await server.listen()
  const origin = server.resolvedUrls?.local[0]
  if (!origin) throw new Error('Vite browser-test server did not expose a local URL')
  testUrl = new URL('/tests/browser/fixtures/cmn-hook-strict-mode.html', origin).href
}, 20_000)

afterAll(async () => {
  await server?.close()
  if (browserProfile) await rm(browserProfile, { recursive: true, force: true })
})

describe('CMN hook lifecycle in real Chromium StrictMode', () => {
  it('applies replayed responses and preserves the correct cancellation rate state', async () => {
    const { stdout } = await dumpBrowserDom(browserExecutable, browserProfile, testUrl, 12_000)

    expect(stdout).toContain('data-complete="true"')
    expect(stdout).toContain('data-strict-eligibility-applied="true"')
    expect(stdout).toContain('data-strict-numbers-applied="true"')
    expect(stdout).toContain('data-first-request-cancel-restored="true"')
    expect(stdout).toContain('data-cooldown-preserved="true"')
    expect(stdout).toContain('data-cooldown-reenabled="true"')
  }, 20_000)
})
