import { execFile } from 'node:child_process'
import { constants as fsConstants } from 'node:fs'
import { access } from 'node:fs/promises'
import { join } from 'node:path'
import process from 'node:process'
import { promisify } from 'node:util'

const executeFile = promisify(execFile)
const browserEnvironmentVariables = ['CHROME_BIN', 'PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH', 'THREEHK_CHROME_BIN']
const browserPathCandidates = ['chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable']

async function isExecutable(filePath, platform) {
  try {
    await access(filePath, platform === 'win32' ? fsConstants.F_OK : fsConstants.X_OK)
    return true
  } catch {
    return false
  }
}

export async function resolveBrowserExecutable(environment = process.env, platform = process.platform) {
  for (const variableName of browserEnvironmentVariables) {
    const configuredPath = environment[variableName]
    if (configuredPath && await isExecutable(configuredPath, platform)) return configuredPath
  }

  const pathSeparator = platform === 'win32' ? ';' : ':'
  const pathDirectories = (environment.PATH ?? '').split(pathSeparator).filter(Boolean)
  const extensions = platform === 'win32' ? (environment.PATHEXT ?? '.EXE;.CMD;.BAT;.COM').split(';') : ['']
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

export async function dumpBrowserDom(browserExecutable, browserProfile, testUrl, virtualTimeBudget = 1000, windowSize) {
  const argumentsList = [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    `--user-data-dir=${browserProfile}`,
    `--virtual-time-budget=${virtualTimeBudget}`,
    '--dump-dom',
    testUrl,
  ]
  if (windowSize) argumentsList.splice(-2, 0, `--window-size=${windowSize}`)
  return executeFile(browserExecutable, argumentsList, { maxBuffer: 1_000_000 })
}
