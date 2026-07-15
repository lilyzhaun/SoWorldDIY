import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useRef } from 'react'

import { useCmnEligibility } from './useCmnEligibility'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function useLifecycle() {
  const mountedRef = useRef(true)
  const scopeGenerationRef = useRef(1)
  return { mountedRef, scopeGenerationRef }
}

describe('useCmnEligibility', () => {
  it('no-ops without subscription id', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => {
      const lifecycle = useLifecycle()
      return useCmnEligibility({
        accountId: 'acc',
        cancelCmnAutoRefresh: vi.fn(),
        currentSubId: '',
        lifecycle,
      })
    })
    await act(async () => {
      await result.current.checkCmnEligibility()
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loads eligibility data on success', async () => {
    document.cookie = ''
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () =>
          JSON.stringify({ status: 'success', data: { offerId: 'o1', price: 10 } }),
        json: async () => ({ status: 'success', data: { offerId: 'o1', price: 10 } }),
      }),
    )
    const { result } = renderHook(() => {
      const lifecycle = useLifecycle()
      return useCmnEligibility({
        accountId: 'acc',
        cancelCmnAutoRefresh: vi.fn(),
        currentSubId: 'sub1',
        lifecycle,
      })
    })
    await act(async () => {
      await result.current.checkCmnEligibility()
    })
    await waitFor(() => {
      expect(result.current.cmnData?.offerId).toBe('o1')
    })
    expect(result.current.cmnLoading).toBe(false)
  })

  it('sets error and cancels auto refresh on failure payload', async () => {
    const cancel = vi.fn()
    document.cookie = ''
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => JSON.stringify({ status: 'error', message: 'nope' }),
        json: async () => ({ status: 'error', message: 'nope' }),
      }),
    )
    const { result } = renderHook(() => {
      const lifecycle = useLifecycle()
      return useCmnEligibility({
        accountId: 'acc',
        cancelCmnAutoRefresh: cancel,
        currentSubId: 'sub1',
        lifecycle,
      })
    })
    await act(async () => {
      await result.current.checkCmnEligibility()
    })
    await waitFor(() => expect(result.current.cmnError).toBe('nope'))
    expect(cancel).toHaveBeenCalledWith(false)
  })

  it('maps network errors to user-facing messages', async () => {
    const cancel = vi.fn()
    document.cookie = ''
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('boom')))
    const { result } = renderHook(() => {
      const lifecycle = useLifecycle()
      return useCmnEligibility({
        accountId: 'acc',
        cancelCmnAutoRefresh: cancel,
        currentSubId: 'sub1',
        lifecycle,
      })
    })
    await act(async () => {
      await result.current.checkCmnEligibility()
    })
    await waitFor(() => expect(result.current.cmnError).toBe('boom'))
    expect(cancel).toHaveBeenCalled()
  })
})
