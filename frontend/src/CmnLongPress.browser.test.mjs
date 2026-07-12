import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { URL, fileURLToPath } from 'node:url'

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { createServer } from 'vite'

import { dumpBrowserDom, resolveBrowserExecutable } from './test-utils/browserHarness.mjs'

const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
let server
let browserProfile
let browserExecutable
let testUrl

beforeAll(async () => {
  browserExecutable = await resolveBrowserExecutable()
  browserProfile = await mkdtemp(join(tmpdir(), '3hk-cmn-browser-'))
  server = await createServer({ root: frontendRoot, logLevel: 'silent', server: { host: '127.0.0.1' } })
  await server.listen()
  const origin = server.resolvedUrls?.local[0]
  if (!origin) throw new Error('Vite browser-test server did not expose a local URL')
  testUrl = new URL('/src/test-fixtures/cmn-long-press.html', origin).href
}, 20_000)

afterAll(async () => {
  await server?.close()
  if (browserProfile) await rm(browserProfile, { recursive: true, force: true })
})

describe('CMN long press in real Chromium', () => {
  it('keeps clicks single, arms only valid patterns, suppresses the compatibility click, cancels explicitly, and highlights the match', async () => {
    const { stdout } = await dumpBrowserDom(browserExecutable, browserProfile, testUrl, 12_000, '375,900')

    expect(stdout).toContain('data-complete="true"')
    expect(stdout).toContain('data-refreshes="3"')
    expect(stdout).toContain('data-starts="3"')
    expect(stdout).toContain('data-cancels-before-explicit-click="0"')
    expect(stdout).toContain('data-cancels="3"')
    expect(stdout).toContain('data-highlighted="true"')
    expect(stdout).toContain('data-empty-contextmenu-prevented="false"')
    expect(stdout).toContain('data-invalid-contextmenu-prevented="false"')
    expect(stdout).toContain('data-right-contextmenu-prevented="false"')
    expect(stdout).toContain('data-armed-contextmenu-prevented="true"')
    expect(stdout).toContain('data-stale-arms-started="0"')
    expect(stdout).toContain('data-keyboard-focused="true"')
    expect(stdout).toContain('data-keyboard-started="true"')
    expect(stdout).toContain('data-grid-shift-ok="true"')
    expect(stdout).toContain('data-actions-shift-ok="true"')
    expect(stdout).toContain('data-button-height-shift-ok="true"')
    expect(stdout).toContain('data-viewport-width="375"')
  }, 20_000)
})
