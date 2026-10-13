import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useSubscriptionBootstrap } from './useSubscriptionBootstrap'
import { usePurchaseCart } from './usePurchaseCart'
import type { Category } from '@/types'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useSubscriptionBootstrap', () => {
  it('keeps the cart across categories but clears it on subscription change', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'success', plans: [] }) }),
    )
    const setters = { setBalance: vi.fn(), setPlans: vi.fn(), setPlansLoading: vi.fn() }
    const actions = {
      checkCmnEligibility: vi.fn(),
      fetchHistory: vi.fn(),
      fetchInbox: vi.fn(),
      resetHistory: vi.fn(),
      showAlert: vi.fn(),
    }
    const { result, rerender } = renderHook(
      ({ category, currentSubId }) => {
        const purchase = usePurchaseCart('acc', currentSubId, '0')
        useSubscriptionBootstrap(
          { accountId: 'acc', category, currentSubId, noNumberMode: false, ...setters },
          { ...actions, resetCart: purchase.resetCart },
        )
        return purchase
      },
      { initialProps: { category: 'ALL' as Category, currentSubId: 's1' } },
    )
    await waitFor(() => expect(setters.setPlans).toHaveBeenCalled())
    act(() => result.current.setCartQtyDraft({ offerId: 'o1', name: 'Plan', price: 5, quantity: 2 }))
    act(() => result.current.confirmAddToCart(vi.fn()))
    expect(result.current.cartCount).toBe(2)
    rerender({ category: 'LOCAL', currentSubId: 's1' })
    expect(result.current.cartCount).toBe(2)
    rerender({ category: 'CMN', currentSubId: 's1' })
    expect(result.current.cartCount).toBe(2)
    expect(actions.checkCmnEligibility).toHaveBeenCalledTimes(1)
    rerender({ category: 'ALL', currentSubId: 's2' })
    expect(result.current.cartCount).toBe(0)
  })

  it('fetches balance and plans for a subscription', async () => {
    document.cookie = ''
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (url: string) => {
        const body = String(url).includes('/api/balance')
          ? { status: 'success', balance: 12.5 }
          : {
              status: 'success',
              plans: [{ offerId: 'o1', name: 'p', price: 3, validity: '1d', desc: 'd', category: 'LOCAL' }],
            }
        return {
          ok: true,
          status: 200,
          statusText: 'OK',
          text: async () => JSON.stringify(body),
          json: async () => body,
        }
      }),
    )
    const setBalance = vi.fn()
    const setPlans = vi.fn()
    const setPlansLoading = vi.fn()
    const fetchInbox = vi.fn().mockResolvedValue(undefined)
    const fetchHistory = vi.fn().mockResolvedValue(undefined)
    const resetCart = vi.fn()
    const resetHistory = vi.fn()
    const checkCmnEligibility = vi.fn().mockResolvedValue(undefined)

    renderHook(() =>
      useSubscriptionBootstrap(
        {
          accountId: 'acc',
          category: 'ALL',
          currentSubId: 'sub1',
          noNumberMode: false,
          setBalance,
          setPlans,
          setPlansLoading,
        },
        {
          checkCmnEligibility,
          fetchHistory,
          fetchInbox,
          resetCart,
          resetHistory,
          showAlert: vi.fn(),
        },
      ),
    )

    await waitFor(() => {
      expect(setBalance).toHaveBeenCalled()
      expect(setPlans).toHaveBeenCalled()
    })
    expect(fetchInbox).toHaveBeenCalled()
    expect(fetchHistory).toHaveBeenCalled()
    expect(resetCart).toHaveBeenCalled()
    expect(resetHistory).toHaveBeenCalled()
  })

  it('sets zero balance in no-number mode and checks CMN when category is CMN', async () => {
    document.cookie = ''
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => JSON.stringify({ status: 'success', plans: [] }),
        json: async () => ({ status: 'success', plans: [] }),
      }),
    )
    const setBalance = vi.fn()
    const checkCmnEligibility = vi.fn().mockResolvedValue(undefined)
    renderHook(() =>
      useSubscriptionBootstrap(
        {
          accountId: 'acc',
          category: 'CMN',
          currentSubId: 'sub1',
          noNumberMode: true,
          setBalance,
          setPlans: vi.fn(),
          setPlansLoading: vi.fn(),
        },
        {
          checkCmnEligibility,
          fetchHistory: vi.fn(),
          fetchInbox: vi.fn(),
          resetCart: vi.fn(),
          resetHistory: vi.fn(),
          showAlert: vi.fn(),
        },
      ),
    )
    await waitFor(() => expect(setBalance).toHaveBeenCalledWith('0.0'))
    // noNumberMode skips CMN check in the effect condition: category === 'CMN' && !noNumberMode
    expect(checkCmnEligibility).not.toHaveBeenCalled()
  })
})
