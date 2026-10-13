import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useProfileBootstrap } from './useProfileBootstrap'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useProfileBootstrap', () => {
  it('redirects a session conflict to a clearly explained login without retry', async () => {
    const original = window.location
    Object.defineProperty(window, 'location', { configurable: true, value: { ...original, href: '' } })
    const fetch = vi.fn().mockResolvedValue({
      status: 409,
      ok: false,
      headers: { get: () => 'application/json' },
    })
    vi.stubGlobal('fetch', fetch)
    try {
      renderHook(() =>
        useProfileBootstrap({
          accountId: 'account',
          currentSubId: '',
          setCurrentSubId: vi.fn(),
          setNoNumberMode: vi.fn(),
          setLoading: vi.fn(),
          setSubscriptions: vi.fn(),
          setAvailableAccounts: vi.fn(),
        }),
      )
      await waitFor(() => expect(window.location.href).toBe('/?session=expired'))
      expect(fetch).toHaveBeenCalledTimes(1)
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: original })
    }
  })
  it('loads profile and selects subscription', async () => {
    const setCurrentSubId = vi.fn()
    const setNoNumberMode = vi.fn()
    const setLoading = vi.fn()
    const setSubscriptions = vi.fn()
    const setAvailableAccounts = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        redirected: false,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          status: 'success',
          data: {
            subscriptions: [{ subscriptionId: 'sub1' }],
            current: { subscriptionId: 'sub1' },
            available_accounts: [{ identifier: 'a@b.com', active: true, subBrand: 'THREE' }],
          },
        }),
      }),
    )
    document.cookie = ''
    renderHook(() =>
      useProfileBootstrap({
        accountId: 'a@b.com',
        currentSubId: '',
        setCurrentSubId,
        setNoNumberMode,
        setLoading,
        setSubscriptions,
        setAvailableAccounts,
      }),
    )
    await waitFor(() => {
      expect(setSubscriptions).toHaveBeenCalled()
      expect(setLoading).toHaveBeenCalledWith(false)
    })
    expect(setCurrentSubId).toHaveBeenCalledWith('sub1')
    expect(setAvailableAccounts).toHaveBeenCalled()
  })

  it('enables no-number mode when no subscriptions', async () => {
    const setNoNumberMode = vi.fn()
    const setLoading = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        redirected: false,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          status: 'success',
          data: { subscriptions: [], available_accounts: [] },
        }),
      }),
    )
    document.cookie = ''
    renderHook(() =>
      useProfileBootstrap({
        accountId: 'a@b.com',
        currentSubId: '',
        setCurrentSubId: vi.fn(),
        setNoNumberMode,
        setLoading,
        setSubscriptions: vi.fn(),
        setAvailableAccounts: vi.fn(),
      }),
    )
    await waitFor(() => expect(setNoNumberMode).toHaveBeenCalledWith(true))
  })
})
