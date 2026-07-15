import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PROFILE_REFRESH_COMPLETION_DELAY_MS, useProfileRefresh } from './useProfileRefresh'

const apiGet = vi.hoisted(() => vi.fn())
vi.mock('@/api/client', () => ({ apiGet }))
vi.mock('@/utils/mainPage', () => ({
  getApiUrl: (path: string) => path,
}))

describe('useProfileRefresh', () => {
  beforeEach(() => {
    apiGet.mockReset()
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('refreshes profile data on success', async () => {
    const setAvailableAccounts = vi.fn()
    const setSubscriptions = vi.fn()
    const showAlert = vi.fn()
    apiGet.mockResolvedValueOnce({
      status: 'success',
      data: {
        subscriptions: [{ id: 's1' }],
        available_accounts: [{ id: 'a1' }],
      },
    })

    const { result } = renderHook(() =>
      useProfileRefresh({
        accountId: 'a1',
        setAvailableAccounts,
        setSubscriptions,
        showAlert,
      }),
    )

    await act(async () => {
      const p = result.current.refreshProfileData()
      await p
    })
    expect(setSubscriptions).toHaveBeenCalledWith([{ id: 's1' }])
    expect(setAvailableAccounts).toHaveBeenCalledWith([{ id: 'a1' }])
    expect(result.current.refreshingUsage).toBe(true)

    act(() => {
      vi.advanceTimersByTime(PROFILE_REFRESH_COMPLETION_DELAY_MS)
    })
    expect(result.current.refreshingUsage).toBe(false)
  })

  it('alerts on non-success status and network failure', async () => {
    const showAlert = vi.fn()
    const setAvailableAccounts = vi.fn()
    const setSubscriptions = vi.fn()
    apiGet.mockResolvedValueOnce({ status: 'fail' })

    const { result } = renderHook(() =>
      useProfileRefresh({
        accountId: 'a1',
        setAvailableAccounts,
        setSubscriptions,
        showAlert,
      }),
    )

    await act(async () => {
      await result.current.refreshProfileData()
    })
    expect(showAlert).toHaveBeenCalledWith('刷新失败')

    apiGet.mockRejectedValueOnce(new Error('net'))
    await act(async () => {
      await result.current.refreshProfileData()
    })
    expect(showAlert).toHaveBeenCalledWith('网络连接失败')
  })
})
