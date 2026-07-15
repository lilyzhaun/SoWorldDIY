import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useHistory } from './useHistory'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useHistory', () => {
  it('no-ops fetch when subscription id is empty', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useHistory('acc', ''))
    await act(async () => {
      await result.current.fetchHistory(true, false, vi.fn())
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loads history items on success and caches them', async () => {
    const showAlert = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () =>
          JSON.stringify({
            status: 'success',
            data: [{ transactionDate: '2026-01-01', type: 'PURCHASE' }],
          }),
        json: async () => ({
          status: 'success',
          data: [{ transactionDate: '2026-01-01', type: 'PURCHASE' }],
        }),
      }),
    )
    document.cookie = 'csrf_token=tok'

    const { result } = renderHook(() => useHistory('acc@x.com', 'sub1'))
    await act(async () => {
      await result.current.fetchHistory(true, false, showAlert)
    })
    await waitFor(() => {
      expect(result.current.historyItems).toHaveLength(1)
    })
    expect(showAlert).not.toHaveBeenCalled()

    // second non-manual call uses cache (no extra fetch needed for same key after first)
    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length
    await act(async () => {
      await result.current.fetchHistory(false, true, showAlert)
    })
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(calls)
  })

  it('alerts on failed history payload', async () => {
    const showAlert = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => JSON.stringify({ status: 'error', message: 'bad' }),
        json: async () => ({ status: 'error', message: 'bad' }),
      }),
    )
    document.cookie = 'csrf_token=tok'
    const { result } = renderHook(() => useHistory('acc', 'sub1'))
    await act(async () => {
      await result.current.fetchHistory(true, false, showAlert)
    })
    expect(showAlert).toHaveBeenCalledWith('bad')
  })

  it('alerts network error and supports open/reset', async () => {
    const showAlert = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
    document.cookie = 'csrf_token=tok'
    const { result } = renderHook(() => useHistory('acc', 'sub1'))
    await act(async () => {
      await result.current.openHistory(showAlert)
    })
    expect(result.current.historyOpen).toBe(true)
    expect(showAlert).toHaveBeenCalledWith('网络错误')
    act(() => {
      result.current.resetHistory()
      result.current.setHistoryDetailIndex(2)
      result.current.setHistoryOpen(false)
    })
    expect(result.current.historyItems).toEqual([])
    expect(result.current.historyDetailIndex).toBe(2)
    expect(result.current.historyOpen).toBe(false)
  })
})
