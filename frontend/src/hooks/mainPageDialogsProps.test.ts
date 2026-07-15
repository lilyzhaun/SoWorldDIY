import { describe, expect, it, vi } from 'vitest'

import { buildMainPageDialogs } from './mainPageDialogsProps'

describe('buildMainPageDialogs', () => {
  it('wires dialog props and action callbacks', () => {
    const setCartQtyDraft = vi.fn()
    const openCartModal = vi.fn()
    const confirmAddToCart = vi.fn()
    const onCheckout = vi.fn()
    const onConfirmPurchase = vi.fn()
    const onConfirmTransfer = vi.fn()
    const onSwitchSubscription = vi.fn()
    const setPurchaseDraft = vi.fn()
    const removeCartItem = vi.fn()
    const updateCartItem = vi.fn()

    const props = buildMainPageDialogs({
      availableAccounts: [{ identifier: 'a@b.com', active: true, subBrand: 'THREE' }],
      balance: '10',
      currentSubId: 'sub1',
      showFreePlans: false,
      subscriptions: [{ subscriptionId: 'sub1' }],
      cart: [{ offerId: 'o1', name: 'plan', price: 1, quantity: 1 }],
      cartCount: 1,
      cartTotal: 1,
      purchaseDraft: null,
      transferSubmitting: false,
      removeCartItem,
      updateCartItem,
      setPurchaseDraft,
      setCartQtyDraft,
      confirmAddToCart,
      openCartModal,
      onCheckout,
      onConfirmPurchase,
      onConfirmTransfer,
      frame: {} as never,
      inbox: {} as never,
      history: {} as never,
      quantityPresence: {} as never,
      transfer: {} as never,
      onSwitchSubscription,
      closeCustomModal: vi.fn(),
    })

    expect(props.cart.total).toBe(1)
    expect(props.cartFab.count).toBe(1)
    props.cartFab.onOpen()
    expect(openCartModal).toHaveBeenCalledWith(1)
    props.quantity.onCancel()
    expect(setCartQtyDraft).toHaveBeenCalledWith(null)
    props.quantity.onConfirm()
    expect(confirmAddToCart).toHaveBeenCalled()
    props.actions.onCheckout()
    expect(onCheckout).toHaveBeenCalled()
    props.actions.onConfirmPurchase()
    expect(onConfirmPurchase).toHaveBeenCalled()
    props.actions.onConfirmTransfer()
    expect(onConfirmTransfer).toHaveBeenCalled()
  })
})
