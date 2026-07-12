import { afterEach, describe, expect, it, vi } from 'vitest'

import { runCmnAutoRefresh, type CmnAutoRefreshRequest } from './cmnAutoRefresh'

const nonMatch = { kind: 'success', numbers: ['12345678'] } as const

describe('runCmnAutoRefresh', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts the next request only after the full 3000ms cooldown', async () => {
    vi.useFakeTimers()
    const request = vi.fn<CmnAutoRefreshRequest>().mockResolvedValue(nonMatch)
    const controller = new AbortController()

    const running = runCmnAutoRefresh({ pattern: '666', request, signal: controller.signal })
    await Promise.resolve()
    await vi.advanceTimersByTimeAsync(2999)
    expect(request).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(1)
    expect(request).toHaveBeenCalledTimes(2)
    controller.abort()
    await running
  })

  it('stops at the first candidate matched by the shared CMN matcher', async () => {
    vi.useFakeTimers()
    let requestCount = 0
    const request = vi.fn<CmnAutoRefreshRequest>().mockImplementation(async () => {
      requestCount += 1
      return requestCount === 1 ? nonMatch : { kind: 'success', numbers: ['66612345'] }
    })

    const running = runCmnAutoRefresh({ pattern: '^666', request, signal: new AbortController().signal })
    await Promise.resolve()
    await vi.runAllTimersAsync()

    await expect(running).resolves.toEqual({ kind: 'matched', attempts: 2 })
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('starts exactly 20 sequential requests without a trailing cooldown', async () => {
    vi.useFakeTimers()
    let activeRequests = 0
    let maximumActiveRequests = 0
    const request = vi.fn<CmnAutoRefreshRequest>().mockImplementation(async () => {
      activeRequests += 1
      maximumActiveRequests = Math.max(maximumActiveRequests, activeRequests)
      await Promise.resolve()
      activeRequests -= 1
      return nonMatch
    })

    const running = runCmnAutoRefresh({ pattern: '666', request, signal: new AbortController().signal })
    await Promise.resolve()
    await vi.advanceTimersByTimeAsync(19 * 3000)

    await expect(running).resolves.toEqual({ kind: 'exhausted', attempts: 20 })
    expect(request).toHaveBeenCalledTimes(20)
    expect(maximumActiveRequests).toBe(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('stops when a candidate matches a capture/backreference pattern', async () => {
    vi.useFakeTimers()
    let requestCount = 0
    const request = vi.fn<CmnAutoRefreshRequest>().mockImplementation(async () => {
      requestCount += 1
      return requestCount === 1 ? nonMatch : { kind: 'success', numbers: ['77777777'] }
    })

    const running = runCmnAutoRefresh({
      pattern: '([0-9])\\1{2}',
      request,
      signal: new AbortController().signal,
    })

    await Promise.resolve()
    await vi.advanceTimersByTimeAsync(3000)

    await expect(running).resolves.toEqual({ kind: 'matched', attempts: 2 })
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('aborts while a request is pending and ignores its late resolution', async () => {
    let resolveRequest: ((value: typeof nonMatch) => void) | undefined
    const request = vi.fn<CmnAutoRefreshRequest>().mockImplementation(() => new Promise((resolve) => {
      resolveRequest = resolve
    }))
    const controller = new AbortController()

    const running = runCmnAutoRefresh({ pattern: '666', request, signal: controller.signal })
    controller.abort()
    resolveRequest?.(nonMatch)

    await expect(running).resolves.toEqual({ kind: 'aborted', attempts: 1 })
    expect(request).toHaveBeenCalledTimes(1)
  })

  it('aborts during cooldown without starting another request', async () => {
    vi.useFakeTimers()
    const request = vi.fn<CmnAutoRefreshRequest>().mockResolvedValue(nonMatch)
    const controller = new AbortController()

    const running = runCmnAutoRefresh({ pattern: '666', request, signal: controller.signal })
    await Promise.resolve()
    await vi.advanceTimersByTimeAsync(2999)
    controller.abort()
    await vi.runAllTimersAsync()

    await expect(running).resolves.toEqual({ kind: 'aborted', attempts: 1 })
    expect(request).toHaveBeenCalledTimes(1)
  })

  it.each([
    [{ kind: 'unavailable' } as const, { kind: 'unavailable', attempts: 1 } as const],
    [{ kind: 'error' } as const, { kind: 'error', attempts: 1 } as const],
  ])('stops when a request returns %s', async (outcome, expected) => {
    const request = vi.fn<CmnAutoRefreshRequest>().mockResolvedValue(outcome)

    await expect(runCmnAutoRefresh({ pattern: '666', request, signal: new AbortController().signal })).resolves.toEqual(expected)
    expect(request).toHaveBeenCalledTimes(1)
  })

  it('converts a rejected request into an error result', async () => {
    const request = vi.fn<CmnAutoRefreshRequest>().mockRejectedValue(new TypeError('network failed'))

    await expect(runCmnAutoRefresh({ pattern: '666', request, signal: new AbortController().signal })).resolves.toEqual({ kind: 'error', attempts: 1 })
  })
})
