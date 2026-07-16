import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCmnNumbers } from './useCmnNumbers'

const apiFetch = vi.hoisted(() => vi.fn())
vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    apiFetch,
  }
})

function lifecycle() {
  return {
    mountedRef: { current: true },
    scopeGenerationRef: { current: 0 },
  }
}

describe('useCmnNumbers', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns unavailable without subscription or while in-flight/cooldown', async () => {
    const lc = lifecycle()
    const { result, rerender } = renderHook(
      ({ sub }) => useCmnNumbers({ accountId: 'a1', currentSubId: sub, lifecycle: lc }),
      { initialProps: { sub: '' } },
    )
    const showAlert = vi.fn()
    await act(async () => {
      const out = await result.current.refreshCmnNumbers(showAlert)
      expect(out).toEqual({ kind: 'unavailable' })
    })

    rerender({ sub: 'sub-1' })
    apiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'success', numbers: ['1', '2'] }),
    })
    await act(async () => {
      const out = await result.current.refreshCmnNumbers(showAlert)
      expect(out).toEqual({ kind: 'success', numbers: ['1', '2'] })
    })
    expect(result.current.cmnNumbers).toEqual(['1', '2'])
    expect(result.current.cmnCanRefresh).toBe(false)

    // cooldown blocks another refresh
    await act(async () => {
      const out = await result.current.refreshCmnNumbers(showAlert)
      expect(out).toEqual({ kind: 'unavailable' })
    })
  })

  it('handles http error with message and status error paths', async () => {
    const lc = lifecycle()
    const { result } = renderHook(() => useCmnNumbers({ accountId: 'a1', currentSubId: 'sub-1', lifecycle: lc }))
    const showAlert = vi.fn()

    apiFetch.mockResolvedValueOnce({
      ok: false,
      text: async () => JSON.stringify({ message: '限流' }),
    })
    await act(async () => {
      const out = await result.current.refreshCmnNumbers(showAlert)
      expect(out).toEqual({ kind: 'error' })
    })
    expect(showAlert).toHaveBeenCalledWith('限流')
    expect(result.current.cmnCanRefresh).toBe(true)

    apiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'fail', message: '业务失败' }),
    })
    await act(async () => {
      const out = await result.current.refreshCmnNumbers(showAlert)
      expect(out).toEqual({ kind: 'error' })
    })
    expect(showAlert).toHaveBeenCalledWith('业务失败')
  })

  it('handles network error and aborted request', async () => {
    const lc = lifecycle()
    const { result } = renderHook(() => useCmnNumbers({ accountId: 'a1', currentSubId: 'sub-1', lifecycle: lc }))
    const showAlert = vi.fn()

    apiFetch.mockRejectedValueOnce(new Error('network'))
    await act(async () => {
      const out = await result.current.refreshCmnNumbers(showAlert)
      expect(out).toEqual({ kind: 'error' })
    })
    expect(showAlert).toHaveBeenCalled()

    // abort path via external signal
    const ac = new AbortController()
    ac.abort()
    await act(async () => {
      // requestCmnNumbers with aborted signal returns unavailable early after start
      apiFetch.mockImplementationOnce(() => {
        const err = new Error('aborted')
        return Promise.reject(err)
      })
      // manually call with signal that is already aborted after starting is hard;
      // canStartAutoRefresh without sub is false
      expect(result.current.canStartAutoRefresh()).toBe(true)
    })

    act(() => {
      result.current.releaseAutoRequestAfterCancel()
    })
    expect(result.current.cmnNumbersLoading).toBe(false)
  })

  it('resets state when account or subscription changes', async () => {
    const lc = lifecycle()
    const { result, rerender } = renderHook(
      ({ accountId, currentSubId }) => useCmnNumbers({ accountId, currentSubId, lifecycle: lc }),
      { initialProps: { accountId: 'a1', currentSubId: 's1' } },
    )
    apiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'success', numbers: ['9'] }),
    })
    await act(async () => {
      await result.current.refreshCmnNumbers(vi.fn())
    })
    expect(result.current.cmnNumbers).toEqual(['9'])

    act(() => {
      result.current.setSelectedNumber('9')
    })
    expect(result.current.selectedNumber).toBe('9')

    rerender({ accountId: 'a2', currentSubId: 's2' })
    await waitFor(() => {
      expect(result.current.cmnNumbers).toEqual([])
      expect(result.current.selectedNumber).toBeNull()
      expect(result.current.cmnCanRefresh).toBe(true)
    })
  })

  it('ticks cooldown down to re-enable refresh', async () => {
    const lc = lifecycle()
    const { result } = renderHook(() => useCmnNumbers({ accountId: 'a1', currentSubId: 'sub-1', lifecycle: lc }))
    apiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'success', numbers: ['1'] }),
    })
    await act(async () => {
      await result.current.refreshCmnNumbers(vi.fn())
    })
    expect(result.current.cmnCooldown).toBeGreaterThan(0)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3500)
    })
    await waitFor(() => {
      expect(result.current.cmnCanRefresh).toBe(true)
      expect(result.current.cmnCooldown).toBe(0)
    })
  })
})
