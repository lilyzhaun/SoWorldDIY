import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useInbox } from './useInbox'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useInbox', () => {
  it('loads messages on open and skips refetch when cached', async () => {
    const showAlert = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      text: async () =>
        JSON.stringify({
          status: 'success',
          messages: [
            {
              subject: 's',
              content: 'c',
              post_dt: 't',
              intended_subscription_id: '1',
            },
          ],
        }),
      json: async () => ({
        status: 'success',
        messages: [
          {
            subject: 's',
            content: 'c',
            post_dt: 't',
            intended_subscription_id: '1',
          },
        ],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)
    document.cookie = ''

    const { result } = renderHook(() => useInbox('acc'))
    await act(async () => {
      await result.current.openInbox(showAlert)
    })
    await waitFor(() => expect(result.current.inboxMessages).toHaveLength(1))
    const calls = fetchMock.mock.calls.length
    await act(async () => {
      await result.current.fetchInbox(false, showAlert)
    })
    expect(fetchMock.mock.calls.length).toBe(calls)
  })

  it('alerts on failure when inbox is open', async () => {
    const showAlert = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
    document.cookie = ''
    const { result } = renderHook(() => useInbox('acc'))
    act(() => {
      result.current.setInboxOpen(true)
    })
    await act(async () => {
      await result.current.fetchInbox(true, showAlert)
    })
    expect(showAlert).toHaveBeenCalledWith('加载失败')
  })
})
