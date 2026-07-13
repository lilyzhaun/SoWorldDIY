import { chmod, mkdtemp, rm, writeFile } from 'node:fs/promises'
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

describe('browser executable resolver', () => {
  it('prefers an explicit accepted environment variable over PATH', async () => {
    const directory = await mkdtemp(join(tmpdir(), '3hk-browser-resolver-'))
    const explicitBrowser = join(directory, 'explicit-chrome')
    const pathBrowser = join(directory, 'chromium')
    await Promise.all([writeFile(explicitBrowser, ''), writeFile(pathBrowser, '')])
    await Promise.all([chmod(explicitBrowser, 0o755), chmod(pathBrowser, 0o755)])

    await expect(
      resolveBrowserExecutable({ THREEHK_CHROME_BIN: explicitBrowser, PATH: directory }, 'linux'),
    ).resolves.toBe(explicitBrowser)
    await rm(directory, { recursive: true, force: true })
  })

  it('finds supported browser candidates directly from PATH', async () => {
    const directory = await mkdtemp(join(tmpdir(), '3hk-browser-resolver-'))
    const pathBrowser = join(directory, 'google-chrome-stable')
    await writeFile(pathBrowser, '')
    await chmod(pathBrowser, 0o755)

    await expect(resolveBrowserExecutable({ PATH: directory }, 'linux')).resolves.toBe(pathBrowser)
    await rm(directory, { recursive: true, force: true })
  })

  it('fails actionably when no accepted browser executable exists', async () => {
    const directory = await mkdtemp(join(tmpdir(), '3hk-browser-resolver-'))

    await expect(resolveBrowserExecutable({ PATH: directory }, 'linux')).rejects.toThrow(
      /CHROME_BIN.*PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH.*THREEHK_CHROME_BIN.*chromium.*google-chrome-stable/s,
    )
    await rm(directory, { recursive: true, force: true })
  })
})

beforeAll(async () => {
  browserExecutable = await resolveBrowserExecutable()
  browserProfile = await mkdtemp(join(tmpdir(), '3hk-inbox-browser-'))
  server = await createServer({ root: frontendRoot, logLevel: 'silent', server: { host: '127.0.0.1' } })
  await server.listen()
  const origin = server.resolvedUrls?.local[0]
  if (!origin) throw new Error('Vite browser-test server did not expose a local URL')
  testUrl = new URL('/tests/browser/fixtures/inbox-sanitization.html', origin).href
}, 20_000)

afterAll(async () => {
  await server?.close()
  if (browserProfile) await rm(browserProfile, { recursive: true, force: true })
})

describe('inbox sanitization in a real browser DOM', () => {
  it('sanitizes malicious HTML and wraps numeric time units without touching attributes', async () => {
    const { stdout } = await dumpBrowserDom(browserExecutable, browserProfile, testUrl)

    expect(stdout).toContain('data-complete="true"')
    expect(stdout).toContain('title="期限60天"')
    expect(stdout).toContain('有效期<span class="inbox-nowrap-token">60天</span>')
    expect(stdout).not.toContain('onerror=')
    expect(stdout).not.toContain('<script>alert(2)')
    expect(stdout).not.toContain('alert(1)')
  }, 20_000)
})
