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
  browserProfile = await mkdtemp(join(tmpdir(), '3hk-cmn-browser-'))
  server = await createServer({ root: frontendRoot, logLevel: 'silent', server: { host: '127.0.0.1' } })
  await server.listen()
  const origin = server.resolvedUrls?.local[0]
  if (!origin) throw new Error('Vite browser-test server did not expose a local URL')
  testUrl = new URL('/tests/browser/fixtures/cmn-long-press.html', origin).href
}, 20_000)

afterAll(async () => {
  await server?.close()
  if (browserProfile) await rm(browserProfile, { recursive: true, force: true })
})

describe('CMN long press in real Chromium', () => {
  it('keeps clicks single, arms only valid patterns, suppresses the compatibility click, cancels explicitly, and highlights the match', async () => {
    const { stdout } = await dumpBrowserDom(browserExecutable, browserProfile, testUrl, 20_000, '375,900')

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
    expect(stdout).toContain('data-keyboard-focus-transferred="true"')
    expect(stdout).toContain('data-keyboard-started="true"')
    expect(stdout).toContain('data-pointer-focus-preserved="true"')
    expect(stdout).toContain('data-grid-shift-ok="true"')
    expect(stdout).toContain('data-actions-shift-ok="true"')
    expect(stdout).toContain('data-button-height-shift-ok="true"')
    expect(stdout).toContain('data-initial-idle-correct="true"')
    expect(stdout).toContain('data-initial-loading-correct="true"')
    expect(stdout).toContain('data-initial-height-stable="true"')
    expect(stdout).toContain('data-subsequent-loading-correct="true"')
    expect(stdout).toContain('data-cooldown-correct="true"')
    expect(stdout).toContain('data-countdown-tabular="true"')
    expect(stdout).toContain('data-zero-seconds-hidden="true"')
    expect(stdout).toContain('data-loading-animation-name="waiting-state-spin"')
    expect(stdout).toContain('data-reduced-motion="false"')
    expect(stdout).toContain('data-viewport-width="500"')
    expect(stdout).toContain('data-root-fills-viewport="true"')
  }, 30_000)

  it.each([768, 1280])(
    'uses the full %ipx responsive viewport',
    async (viewportWidth) => {
      const { stdout } = await dumpBrowserDom(
        browserExecutable,
        browserProfile,
        testUrl,
        20_000,
        `${viewportWidth},900`,
      )

      expect(stdout).toContain('data-complete="true"')
      expect(stdout).toContain(`data-viewport-width="${viewportWidth}"`)
      expect(stdout).toContain('data-root-fills-viewport="true"')
    },
    30_000,
  )

  it('disables refresh rotation when reduced motion is requested', async () => {
    const reducedMotionUrl = new URL(testUrl)
    reducedMotionUrl.searchParams.set('reduced', '1')
    const { stdout } = await dumpBrowserDom(
      browserExecutable,
      browserProfile,
      reducedMotionUrl.href,
      4_000,
      '375,900',
      ['--force-prefers-reduced-motion=reduce'],
    )

    expect(stdout).toContain('data-complete="true"')
    expect(stdout).toContain('data-loading-animation-name="none"')
    expect(stdout).toContain('data-reduced-motion="true"')
  }, 30_000)
})
