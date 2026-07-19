import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { URL, fileURLToPath } from 'node:url'

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { createServer } from 'vite'

import { dumpBrowserDom, resolveBrowserExecutable } from './browserHarness.mjs'

const frontendRoot = fileURLToPath(new URL('../..', import.meta.url))
let server
let browserExecutable
let testUrl

async function dumpState(url, virtualTimeBudget, windowSize, browserArguments = []) {
  const browserProfile = await mkdtemp(join(tmpdir(), '3hk-waiting-state-browser-'))
  try {
    return await dumpBrowserDom(browserExecutable, browserProfile, url, virtualTimeBudget, windowSize, browserArguments)
  } finally {
    await rm(browserProfile, { recursive: true, force: true })
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
  }, 30_000)
})
