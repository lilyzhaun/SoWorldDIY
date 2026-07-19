import { findCmnPatternRanges } from './cmnPattern'

export const CMN_AUTO_REFRESH_MAX_ATTEMPTS = 20
export const CMN_AUTO_REFRESH_COOLDOWN_MS = 3000

export type CmnRefreshOutcome =
  | { readonly kind: 'success'; readonly numbers: readonly string[] }
  | { readonly kind: 'unavailable' }
  | { readonly kind: 'error' }

export type CmnAutoRefreshRequest = (signal: AbortSignal) => Promise<CmnRefreshOutcome>

export type CmnAutoRefreshResult =
  | { readonly kind: 'matched'; readonly attempts: number }
  | { readonly kind: 'exhausted'; readonly attempts: number }
  | { readonly kind: 'aborted'; readonly attempts: number }
  | { readonly kind: 'unavailable'; readonly attempts: number }
  | { readonly kind: 'error'; readonly attempts: number }

export type CmnAutoRefreshPhase = 'requesting' | 'cooldown'

export type CmnAutoRefreshProgress = {
  readonly attempt: number
  readonly phase: CmnAutoRefreshPhase
}

type CmnAutoRefreshOptions = {
  readonly pattern: string
  readonly request: CmnAutoRefreshRequest
  readonly signal: AbortSignal
  readonly onProgress?: (progress: CmnAutoRefreshProgress) => void
}

function waitForCooldown(signal: AbortSignal): Promise<boolean> {
  if (signal.aborted) return Promise.resolve(false)

  return new Promise((resolve) => {
    const timer = globalThis.setTimeout(() => {
      signal.removeEventListener('abort', abort)
      resolve(true)
    }, CMN_AUTO_REFRESH_COOLDOWN_MS)
    const abort = (): void => {
      globalThis.clearTimeout(timer)
      resolve(false)
    }
    signal.addEventListener('abort', abort, { once: true })
  })
}

export async function runCmnAutoRefresh({
  pattern,
  request,
  signal,
  onProgress,
}: CmnAutoRefreshOptions): Promise<CmnAutoRefreshResult> {
  let attempts = 0

  while (attempts < CMN_AUTO_REFRESH_MAX_ATTEMPTS) {
    if (signal.aborted) return { kind: 'aborted', attempts }
    attempts += 1
    onProgress?.({ attempt: attempts, phase: 'requesting' })

    let outcome: CmnRefreshOutcome
    try {
      outcome = await request(signal)
    } catch (error) {
      if (!(error instanceof Error)) throw error
      return signal.aborted ? { kind: 'aborted', attempts } : { kind: 'error', attempts }
    }
    if (signal.aborted) return { kind: 'aborted', attempts }

    switch (outcome.kind) {
      case 'success':
        if (outcome.numbers.some((number) => findCmnPatternRanges(number, pattern).length > 0)) {
          return { kind: 'matched', attempts }
        }
        break
      case 'unavailable':
        return { kind: 'unavailable', attempts }
      case 'error':
        return { kind: 'error', attempts }
      default:
        return outcome satisfies never
    }

    if (attempts === CMN_AUTO_REFRESH_MAX_ATTEMPTS) break
    onProgress?.({ attempt: attempts, phase: 'cooldown' })
    if (!(await waitForCooldown(signal))) return { kind: 'aborted', attempts }
  }

  return { kind: 'exhausted', attempts }
}
