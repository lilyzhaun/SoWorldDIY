import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { usePurchaseCart } from './usePurchaseCart'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('usePurchaseCart', () => {
  it('adds, updates, and removes cart items', () => {
    const showAlert = vi.fn()
    const { result } = renderHook(() => usePurchaseCart('acc', 'sub1', '10'))
    act(() => {
      result.current.openAddToCart({ stopPropagation() {} } as React.MouseEvent, {
        offerId: 'o1',
        name: 'Plan',
        price: 5,
        validity: '1d',
        desc: 'd',
        category: 'LOCAL',
      })
    })
    expect(result.current.cartQtyDraft?.offerId).toBe('o1')
    act(() => {
      result.current.setCartQtyDraft({
        offerId: 'o1',
        name: 'Plan',
        price: 5,
        quantity: 2,
      })
    })
    act(() => {
      result.current.confirmAddToCart(showAlert)
    })
    expect(result.current.cart).toHaveLength(1)
    expect(result.current.cartCount).toBe(2)
    expect(result.current.cartTotal).toBe(10)
    expect(showAlert).toHaveBeenCalled()

    act(() => {
      result.current.updateCartItem(0, 1)
    })
    expect(result.current.cart[0]?.quantity).toBe(3)
    act(() => {
      result.current.updateCartItem(0, -10)
    })
    expect(result.current.cart).toHaveLength(0)

    act(() => {
      result.current.openAddToCart({ stopPropagation() {} } as React.MouseEvent, {
        offerId: 'o2',
        name: 'P2',
        price: 1,
        validity: '1d',
        desc: 'd',
        category: 'LOCAL',
      })
    })
    act(() => {
      result.current.confirmAddToCart(showAlert)
    })
    act(() => {
      result.current.removeCartItem(0)
    })
    expect(result.current.cart).toHaveLength(0)
  })

  it('opens purchase modal with wallet txn amount', () => {
    const openModal = vi.fn()
    const { result } = renderHook(() => usePurchaseCart('acc', 'sub1', '3'))
    act(() => {
      result.current.openPurchaseModal('title', 10, 'cart', openModal)
    })
    expect(openModal).toHaveBeenCalled()
    expect(result.current.purchaseDraft?.txnAmount).toBe(3)
    expect(result.current.purchaseDraft?.source).toBe('cart')
  })

  it('submits checkout and redirects on paymentUrl', async () => {
    const showAlert = vi.fn()
    const href = { value: '' }
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        get href() {
          return href.value
        },
        set href(v: string) {
          href.value = v
        },
      },
    })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => JSON.stringify({ status: 'success', paymentUrl: 'https://pay.example/1' }),
        json: async () => ({ status: 'success', paymentUrl: 'https://pay.example/1' }),
      }),
    )
    document.cookie = 'csrf_token=tok'
    const { result } = renderHook(() => usePurchaseCart('acc', 'sub1', '20'))
    act(() => {
      result.current.openAddToCart({ stopPropagation() {} } as React.MouseEvent, {
        offerId: 'o1',
        name: 'Plan',
        price: 5,
        validity: '1d',
        desc: 'd',
        category: 'LOCAL',
      })
      result.current.confirmAddToCart(vi.fn())
      result.current.openPurchaseModal('t', 5, 'cart', vi.fn())
    })
    await act(async () => {
      await result.current.submitCheckout(showAlert)
    })
    expect(href.value).toBe('https://pay.example/1')
    expect(result.current.cart).toHaveLength(0)
  })

  it('alerts on checkout failure and network errors', async () => {
    const showAlert = vi.fn()
    document.cookie = 'csrf_token=tok'
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
    const { result } = renderHook(() => usePurchaseCart('acc', 'sub1', '20'))
    act(() => {
      result.current.openPurchaseModal('t', 5, 'cart', vi.fn())
    })
    await act(async () => {
      await result.current.submitCheckout(showAlert)
    })
    expect(showAlert).toHaveBeenCalledWith('nope', '错误')

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
    act(() => {
      result.current.openPurchaseModal('t', 5, 'cart', vi.fn())
    })
    await act(async () => {
      await result.current.submitCheckout(showAlert)
    })
    expect(showAlert).toHaveBeenCalledWith('net', '错误')
  })

  it('submits cmn purchase success and failure paths', async () => {
    const showAlert = vi.fn()
    const href = { value: '' }
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        get href() {
          return href.value
        },
        set href(v: string) {
          href.value = v
        },
      },
    })
    document.cookie = 'csrf_token=tok'
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => JSON.stringify({ status: 'success', paymentUrl: 'https://pay.example/cmn' }),
        json: async () => ({ status: 'success', paymentUrl: 'https://pay.example/cmn' }),
      }),
    )
    const { result } = renderHook(() => usePurchaseCart('acc', 'sub1', '20'))
    act(() => {
      result.current.openPurchaseModal('cmn', 8, 'cmn', vi.fn())
    })
    await act(async () => {
      await result.current.submitCmnPurchase(
        { offerId: 'off', offerSubType: 't', price: 8 } as never,
        '51234567',
        showAlert,
      )
    })
    expect(href.value).toBe('https://pay.example/cmn')

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => JSON.stringify({ status: 'error', message: 'cmn fail' }),
        json: async () => ({ status: 'error', message: 'cmn fail' }),
      }),
    )
    act(() => {
      result.current.openPurchaseModal('cmn', 8, 'cmn', vi.fn())
    })
    await act(async () => {
      await result.current.submitCmnPurchase(
        { offerId: 'off', offerSubType: 't', price: 8 } as never,
        '51234567',
        showAlert,
      )
    })
    expect(showAlert).toHaveBeenCalledWith('cmn fail', '失败')
  })
})
