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
  browserProfile = await mkdtemp(join(tmpdir(), '3hk-cmn-scope-browser-'))
  server = await createServer({ root: frontendRoot, logLevel: 'silent', server: { host: '127.0.0.1' } })
  await server.listen()
  const origin = server.resolvedUrls?.local[0]
  if (!origin) throw new Error('Vite browser-test server did not expose a local URL')
  testUrl = new URL('/tests/browser/fixtures/cmn-hook-scope.html', origin).href
}, 20_000)

afterAll(async () => {
  await server?.close()
  if (browserProfile) await rm(browserProfile, { recursive: true, force: true })
})

describe('CMN hook scope lifecycle in real Chromium', () => {
  it('isolates scopes, prevents overlap, preserves abort semantics, and resets cancellation state', async () => {
    const { stdout } = await dumpBrowserDom(browserExecutable, browserProfile, testUrl, 12_000)

    expect(stdout).toContain('data-complete="true"')
    expect(stdout).toContain('data-manual-cleared="true"')
    expect(stdout).toContain('data-non-overlap="true"')
    expect(stdout).toContain('data-scope-reset="true"')
    expect(stdout).toContain('data-old-eligibility-aborted="true"')
    expect(stdout).toContain('data-old-numbers-aborted="false"')
    expect(stdout).toContain('data-stale-ignored="true"')
    expect(stdout).toContain('data-new-scope-applied="true"')
    expect(stdout).toContain('data-exact-cooldown="true"')
    expect(stdout).toContain('data-cooldown-reenabled="true"')
    expect(stdout).toContain('data-auto-loading="true"')
    expect(stdout).toContain('data-auto-request-aborted="true"')
    expect(stdout).toContain('data-cancel-reset="true"')
    expect(stdout).toContain('/api/cmn/check?subscriptionId=subscription-1&amp;account_id=account-1')
    expect(stdout).toContain('/api/cmn/numbers?subscriptionId=subscription-2&amp;account_id=account-2')
  }, 20_000)
})
