import { execFile } from 'node:child_process'
import { constants as fsConstants } from 'node:fs'
import { access, chmod, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import process from 'node:process'
import { URL, fileURLToPath } from 'node:url'
import { promisify } from 'node:util'

import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { createServer } from 'vite'

const executeFile = promisify(execFile)
const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
const browserEnvironmentVariables = ['CHROME_BIN', 'PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH', 'THREEHK_CHROME_BIN']
const browserPathCandidates = ['chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable']
let server
let browserProfile
let browserExecutable
let testUrl

async function isExecutable(filePath, platform) {
  try {
    await access(filePath, platform === 'win32' ? fsConstants.F_OK : fsConstants.X_OK)
    return true
  } catch {
    return false
  }
}

async function resolveBrowserExecutable(environment = process.env, platform = process.platform) {
  for (const variableName of browserEnvironmentVariables) {
    const configuredPath = environment[variableName]
    if (configuredPath && await isExecutable(configuredPath, platform)) return configuredPath
  }

  const pathSeparator = platform === 'win32' ? ';' : ':'
  const pathDirectories = (environment.PATH ?? '').split(pathSeparator).filter(Boolean)
  const extensions = platform === 'win32'
    ? (environment.PATHEXT ?? '.EXE;.CMD;.BAT;.COM').split(';')
    : ['']
  for (const directory of pathDirectories) {
    const normalizedDirectory = directory.replace(/^"|"$/g, '')
    for (const candidate of browserPathCandidates) {
      for (const extension of extensions) {
        const candidatePath = join(normalizedDirectory, `${candidate}${extension}`)
        if (await isExecutable(candidatePath, platform)) return candidatePath
      }
    }
  }

  throw new Error(`Chromium browser executable not found. Set one of ${browserEnvironmentVariables.join(', ')} to an executable path, or install one of these PATH candidates: ${browserPathCandidates.join(', ')}.`)
}

describe('browser executable resolver', () => {
  it('prefers an explicit accepted environment variable over PATH', async () => {
    const directory = await mkdtemp(join(tmpdir(), '3hk-browser-resolver-'))
    const explicitBrowser = join(directory, 'explicit-chrome')
    const pathBrowser = join(directory, 'chromium')
    await Promise.all([writeFile(explicitBrowser, ''), writeFile(pathBrowser, '')])
    await Promise.all([chmod(explicitBrowser, 0o755), chmod(pathBrowser, 0o755)])

    await expect(resolveBrowserExecutable({ THREEHK_CHROME_BIN: explicitBrowser, PATH: directory }, 'linux')).resolves.toBe(explicitBrowser)
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

    await expect(resolveBrowserExecutable({ PATH: directory }, 'linux')).rejects.toThrow(/CHROME_BIN.*PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH.*THREEHK_CHROME_BIN.*chromium.*google-chrome-stable/s)
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
  testUrl = new URL('/src/test-fixtures/inbox-sanitization.html', origin).href
}, 20_000)

afterAll(async () => {
  await server?.close()
  if (browserProfile) await rm(browserProfile, { recursive: true, force: true })
})

describe('inbox sanitization in a real browser DOM', () => {
  it('sanitizes malicious HTML and wraps numeric time units without touching attributes', async () => {
    const { stdout } = await executeFile(browserExecutable, ['--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', `--user-data-dir=${browserProfile}`, '--dump-dom', testUrl], { maxBuffer: 1_000_000 })

    expect(stdout).toContain('data-complete="true"')
    expect(stdout).toContain('title="期限60天"')
    expect(stdout).toContain('有效期<span class="inbox-nowrap-token">60天</span>')
    expect(stdout).not.toContain('onerror=')
    expect(stdout).not.toContain('<script>alert(2)')
    expect(stdout).not.toContain('alert(1)')
  }, 20_000)
})
