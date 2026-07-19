import { afterEach, describe, expect, it, vi } from 'vitest'

import { CMN_AUTO_REFRESH_COOLDOWN_MS, CMN_AUTO_REFRESH_MAX_ATTEMPTS, runCmnAutoRefresh } from './cmnAutoRefresh'

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('runCmnAutoRefresh', () => {
  it('returns matched when a number matches the pattern', async () => {
    const result = await runCmnAutoRefresh({
      pattern: '1234',
      request: async () => ({ kind: 'success', numbers: ['51234123'] }),
      signal: new AbortController().signal,
    })
    expect(result).toEqual({ kind: 'matched', attempts: 1 })
  })

  it('returns unavailable and error outcomes immediately', async () => {
    await expect(
      runCmnAutoRefresh({
        pattern: '99',
        request: async () => ({ kind: 'unavailable' }),
        signal: new AbortController().signal,
      }),
    ).resolves.toEqual({ kind: 'unavailable', attempts: 1 })

    await expect(
      runCmnAutoRefresh({
        pattern: '99',
        request: async () => ({ kind: 'error' }),
        signal: new AbortController().signal,
      }),
    ).resolves.toEqual({ kind: 'error', attempts: 1 })
  })

  it('returns aborted when signal is already aborted', async () => {
    const controller = new AbortController()
    controller.abort()
    await expect(
      runCmnAutoRefresh({
        pattern: '12',
        request: async () => ({ kind: 'success', numbers: ['12'] }),
        signal: controller.signal,
      }),
    ).resolves.toEqual({ kind: 'aborted', attempts: 0 })
  })

  it('returns error when request throws a non-abort Error', async () => {
    await expect(
      runCmnAutoRefresh({
        pattern: '12',
        request: async () => {
          throw new Error('network')
        },
        signal: new AbortController().signal,
      }),
    ).resolves.toEqual({ kind: 'error', attempts: 1 })
  })

  it('exhausts attempts when numbers never match', async () => {
    vi.useFakeTimers()
    const onProgress = vi.fn()
    const promise = runCmnAutoRefresh({
      pattern: '9999',
      request: async () => ({ kind: 'success', numbers: ['11111111'] }),
      signal: new AbortController().signal,
      onProgress,
    })
    // advance cooldowns between attempts
    for (let i = 0; i < CMN_AUTO_REFRESH_MAX_ATTEMPTS; i += 1) {
      await vi.advanceTimersByTimeAsync(CMN_AUTO_REFRESH_COOLDOWN_MS)
    }
    await expect(promise).resolves.toEqual({
      kind: 'exhausted',
      attempts: CMN_AUTO_REFRESH_MAX_ATTEMPTS,
    })
    expect(onProgress).toHaveBeenCalledWith({ attempt: 1, phase: 'requesting' })
    expect(onProgress).toHaveBeenCalledWith({ attempt: 1, phase: 'cooldown' })
    expect(onProgress).toHaveBeenCalledWith({ attempt: CMN_AUTO_REFRESH_MAX_ATTEMPTS, phase: 'requesting' })
    expect(onProgress).not.toHaveBeenCalledWith({ attempt: CMN_AUTO_REFRESH_MAX_ATTEMPTS, phase: 'cooldown' })
  })
})
