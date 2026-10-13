import { URL, fileURLToPath } from 'node:url'

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { createServer } from 'vite'
import { chromium } from 'playwright-core'

import { resolveBrowserExecutable } from './browserHarness.mjs'

const frontendRoot = fileURLToPath(new URL('../..', import.meta.url))
let server
let browserExecutable
let testUrl

async function dumpState(url, completionTimeout, windowSize, browserArguments = []) {
  const [width, height] = windowSize.split(',').map(Number)
  const browser = await chromium.launch({
    executablePath: browserExecutable,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', ...browserArguments],
    timeout: 15_000,
  })
  try {
    const page = await browser.newPage({ viewport: { width, height } })
    await page.emulateMedia({
      reducedMotion: browserArguments.includes('--force-prefers-reduced-motion=reduce') ? 'reduce' : 'no-preference',
    })
    await page.goto(url, { waitUntil: 'load', timeout: 15_000 })
    // CSS animation.finished follows the compositor clock. A virtual-time dump
    // can exit before that promise settles, especially on a loaded CI runner.
    await page.locator('#waiting-state-harness[data-complete="true"]').waitFor({
      state: 'attached',
      timeout: completionTimeout,
    })
    return { stdout: await page.content() }
  } finally {
    await browser.close()
  }
}

function readDataAttribute(stdout, name) {
  const regex = new RegExp(`\\b${name}="([^"]*)"`)
  const match = stdout.match(regex)
  return match?.[1] ?? ''
}

function readNumericDataAttribute(stdout, name) {
  const value = readDataAttribute(stdout, name)
  if (value === '' || value === 'null') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

beforeAll(async () => {
  browserExecutable = await resolveBrowserExecutable()
  server = await createServer({ root: frontendRoot, logLevel: 'silent', server: { host: '127.0.0.1' } })
  await server.listen()
  const origin = server.resolvedUrls?.local[0]
  if (!origin) throw new Error('Vite browser-test server did not expose a local URL')
  testUrl = new URL('/tests/browser/fixtures/waiting-state.html', origin).href
}, 20_000)

afterAll(async () => {
  await server?.close()
})

describe('WaitingState in real Chromium', () => {
  it('naturally finishes quarter-turn primitive animations while linked surfaces remain infinite', async () => {
    const { stdout } = await dumpState(testUrl, 8_000, '375,220')

    expect(stdout).toContain('data-complete="true"')
    expect(readDataAttribute(stdout, 'data-requesting-phase')).toBe('requesting')
    expect(readDataAttribute(stdout, 'data-cooldown-phase')).toBe('cooldown')
    expect(readDataAttribute(stdout, 'data-requesting-animation-name')).toBe('waiting-state-spin')
    expect(readDataAttribute(stdout, 'data-cooldown-animation-name')).toBe('waiting-state-spin')
    expect(readDataAttribute(stdout, 'data-requesting-duration')).toBe('0.75s')
    expect(readDataAttribute(stdout, 'data-cooldown-duration')).toBe('1.5s')
    expect(readDataAttribute(stdout, 'data-requesting-marker')).toBe('true')
    expect(readDataAttribute(stdout, 'data-cooldown-marker')).toBe('true')
    expect(readDataAttribute(stdout, 'data-requesting-icon-visible')).toBe('true')
    expect(readDataAttribute(stdout, 'data-cooldown-icon-visible')).toBe('true')
    expect(readDataAttribute(stdout, 'data-requesting-marker-visible')).toBe('true')
    expect(readDataAttribute(stdout, 'data-cooldown-marker-visible')).toBe('true')
    expect(readDataAttribute(stdout, 'data-reduced-motion')).toBe('false')
    expect(readDataAttribute(stdout, 'data-requesting-visible')).toBe('true')

    const requestInitial = readDataAttribute(stdout, 'data-requesting-initial-transform')
    const requestFinal = readDataAttribute(stdout, 'data-requesting-final-transform')
    const cooldownInitial = readDataAttribute(stdout, 'data-cooldown-initial-transform')
    const cooldownFinal = readDataAttribute(stdout, 'data-cooldown-final-transform')
    expect(requestInitial).not.toBe('')
    expect(requestFinal).not.toBe('')
    expect(cooldownInitial).not.toBe('')
    expect(cooldownFinal).not.toBe('')
    expect(requestFinal).not.toBe(requestInitial)
    expect(cooldownFinal).not.toBe(cooldownInitial)
    const quarterTurn = 'matrix(0, 1, -1, 0, 0, 0)'
    expect(requestFinal).toBe(quarterTurn)
    expect(cooldownFinal).toBe(quarterTurn)
    expect(readNumericDataAttribute(stdout, 'data-requesting-final-current-time')).toBeGreaterThan(0)
    expect(readNumericDataAttribute(stdout, 'data-cooldown-final-current-time')).toBeGreaterThan(0)
    expect(readDataAttribute(stdout, 'data-requesting-final-play-state')).toBe('finished')
    expect(readDataAttribute(stdout, 'data-cooldown-final-play-state')).toBe('finished')
    expect(readDataAttribute(stdout, 'data-requesting-animation-count')).toBe('1')
    expect(readDataAttribute(stdout, 'data-cooldown-animation-count')).toBe('1')

    expect(readDataAttribute(stdout, 'data-planlist-role')).toBe('status')
    expect(readDataAttribute(stdout, 'data-planlist-live')).toBe('polite')
    expect(readDataAttribute(stdout, 'data-planlist-aria-busy')).toBe('true')
    expect(readDataAttribute(stdout, 'data-active-refresh-aria-busy')).toBe('true')

    expect(readDataAttribute(stdout, 'data-cmn-requesting-phase')).toBe('requesting')
    expect(readDataAttribute(stdout, 'data-cmn-cooldown-phase')).toBe('cooldown')
    expect(readDataAttribute(stdout, 'data-cmn-requesting-animation-name')).toBe('waiting-state-spin')
    expect(readDataAttribute(stdout, 'data-cmn-cooldown-animation-name')).toBe('waiting-state-spin')
    expect(readDataAttribute(stdout, 'data-cmn-requesting-duration')).toBe('0.75s')
    expect(readDataAttribute(stdout, 'data-cmn-cooldown-duration')).toBe('1.5s')
    expect(readDataAttribute(stdout, 'data-cmn-requesting-iteration-count')).toBe('infinite')
    expect(readDataAttribute(stdout, 'data-cmn-cooldown-iteration-count')).toBe('infinite')
    expect(readDataAttribute(stdout, 'data-cmn-requesting-animation-count')).toBe('1')
    expect(readDataAttribute(stdout, 'data-cmn-cooldown-animation-count')).toBe('1')
  }, 30_000)

  it('disables animation under reduced-motion while preserving visual markers and phases', async () => {
    const reducedMotionUrl = new URL(testUrl)
    reducedMotionUrl.searchParams.set('reduced', '1')
    const { stdout } = await dumpState(reducedMotionUrl.href, 8_000, '375,220', [
      '--force-prefers-reduced-motion=reduce',
    ])

    expect(stdout).toContain('data-complete="true"')
    expect(readDataAttribute(stdout, 'data-reduced-motion')).toBe('true')
    expect(readDataAttribute(stdout, 'data-requesting-animation-name')).toBe('none')
    expect(readDataAttribute(stdout, 'data-cooldown-animation-name')).toBe('none')
    expect(readDataAttribute(stdout, 'data-cmn-requesting-animation-name')).toBe('none')
    expect(readDataAttribute(stdout, 'data-cmn-cooldown-animation-name')).toBe('none')
    expect(readDataAttribute(stdout, 'data-requesting-animation-count')).toBe('0')
    expect(readDataAttribute(stdout, 'data-cooldown-animation-count')).toBe('0')
    expect(readDataAttribute(stdout, 'data-cmn-requesting-animation-count')).toBe('0')
    expect(readDataAttribute(stdout, 'data-cmn-cooldown-animation-count')).toBe('0')

    const requestInitial = readDataAttribute(stdout, 'data-requesting-initial-transform')
    const requestFinal = readDataAttribute(stdout, 'data-requesting-final-transform')
    const cooldownInitial = readDataAttribute(stdout, 'data-cooldown-initial-transform')
    const cooldownFinal = readDataAttribute(stdout, 'data-cooldown-final-transform')
    const staticTransform = 'matrix(0.707107, 0.707107, -0.707107, 0.707107, 0, 0)'
    expect(requestInitial).toBe(staticTransform)
    expect(requestFinal).toBe(staticTransform)
    expect(cooldownInitial).toBe(staticTransform)
    expect(cooldownFinal).toBe(staticTransform)
    expect(readNumericDataAttribute(stdout, 'data-requesting-final-current-time')).toBe(null)
    expect(readNumericDataAttribute(stdout, 'data-cooldown-final-current-time')).toBe(null)
    expect(readDataAttribute(stdout, 'data-requesting-marker')).toBe('true')
    expect(readDataAttribute(stdout, 'data-cooldown-marker')).toBe('true')
    expect(readDataAttribute(stdout, 'data-requesting-icon-visible')).toBe('true')
    expect(readDataAttribute(stdout, 'data-cooldown-icon-visible')).toBe('true')
    expect(readDataAttribute(stdout, 'data-requesting-marker-visible')).toBe('true')
    expect(readDataAttribute(stdout, 'data-cooldown-marker-visible')).toBe('true')

    expect(readDataAttribute(stdout, 'data-requesting-marker-background')).not.toBe('rgba(0, 0, 0, 0)')
    expect(readDataAttribute(stdout, 'data-requesting-marker-box-shadow')).toBe('none')
    expect(readDataAttribute(stdout, 'data-cooldown-marker-background')).toBe('rgba(0, 0, 0, 0)')
    expect(readDataAttribute(stdout, 'data-cooldown-marker-box-shadow')).toContain('inset')
  }, 30_000)
})
