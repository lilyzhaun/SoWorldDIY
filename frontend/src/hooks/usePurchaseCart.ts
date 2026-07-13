import { useMemo, useState } from 'react'

import { apiPostJson } from '@/api/client'
import type { CartItem, CmnCheckResponse, Plan } from '@/types'
import { toUserFacingApiError } from '@/utils'
import { getApiUrl } from '@/utils/mainPage'

export type CartQuantityDraft = {
  readonly offerId: string
  readonly name: string
  readonly price: number
  readonly quantity: number
}

type PaymentType = 'ALCN' | 'ALHK' | 'WECHAT' | 'MPGS'

export type PurchaseDraft = {
  readonly title: string
  readonly price: number
  readonly txnAmount: number
  readonly paymentType: PaymentType
  readonly submitting: boolean
  readonly source: 'cart' | 'cmn'
  readonly newLine: boolean
}

type ShowAlert = (text: string, title?: string) => void

export function usePurchaseCart(accountId: string, currentSubId: string, balance: string) {
  const [cart, setCart] = useState<CartItem[]>([])
  const [cartQtyDraft, setCartQtyDraft] = useState<CartQuantityDraft | null>(null)
  const [purchaseDraft, setPurchaseDraft] = useState<PurchaseDraft | null>(null)

  const cartCount = useMemo(() => cart.reduce((total, item) => total + item.quantity, 0), [cart])
  const cartTotal = useMemo(() => cart.reduce((total, item) => total + item.price * item.quantity, 0), [cart])

  const openAddToCart = (event: React.MouseEvent, plan: Plan): void => {
    event.stopPropagation()
    const existing = cart.find((item) => item.offerId === plan.offerId)
    setCartQtyDraft({ offerId: plan.offerId, name: plan.name, price: plan.price, quantity: existing?.quantity || 1 })
  }

  const confirmAddToCart = (showAlert: ShowAlert): void => {
    if (!cartQtyDraft) return
    const quantity = Math.max(1, Math.min(99, cartQtyDraft.quantity))
    setCart((previous) => {
      const index = previous.findIndex((item) => item.offerId === cartQtyDraft.offerId)
      if (index >= 0) {
        const next = previous.slice()
        next[index] = { ...next[index], quantity }
        return next
      }
      return [...previous, { offerId: cartQtyDraft.offerId, name: cartQtyDraft.name, price: cartQtyDraft.price, quantity }]
    })
    setCartQtyDraft(null)
    showAlert(`已加入: ${cartQtyDraft.name} x ${quantity}`, '成功')
  }

  const updateCartItem = (index: number, delta: number): void => {
    setCart((previous) => {
      const next = previous.slice()
      next[index] = { ...next[index], quantity: next[index].quantity + delta }
      if (next[index].quantity <= 0) next.splice(index, 1)
      return next
    })
  }

  const removeCartItem = (index: number): void => {
    setCart((previous) => previous.filter((_, itemIndex) => itemIndex !== index))
  }

  const openPurchaseModal = (title: string, price: number, source: 'cart' | 'cmn', openModal: () => void): void => {
    const currentBalance = Number.parseFloat(balance) || 0
    const txnAmount = currentBalance >= price ? price : Math.max(currentBalance, 0)
    setPurchaseDraft({ title, price, txnAmount, paymentType: 'ALCN', submitting: false, source, newLine: false })
    openModal()
  }

  const submitCheckout = async (showAlert: ShowAlert): Promise<void> => {
    if (!purchaseDraft || purchaseDraft.source !== 'cart') return
    setPurchaseDraft((previous) => (previous ? { ...previous, submitting: true } : null))
    try {
      const url = getApiUrl('/api/purchase', accountId)
      const data = await apiPostJson<{ status?: string; message?: string; paymentUrl?: string }>(url, { items: cart, subscriptionId: currentSubId, price: purchaseDraft.price, paymentType: purchaseDraft.paymentType, txnAmount: purchaseDraft.txnAmount, new_line: purchaseDraft.newLine, account_id: accountId })
      if (data.status === 'success' && data.paymentUrl) {
        setCart([])
        window.location.href = data.paymentUrl
      } else {
        showAlert(data.message || '提交失败', '错误')
        setPurchaseDraft((previous) => (previous ? { ...previous, submitting: false } : null))
      }
    } catch (error: unknown) {
      showAlert(toUserFacingApiError(error, '网络错误'), '错误')
      setPurchaseDraft((previous) => (previous ? { ...previous, submitting: false } : null))
    }
  }

  const submitCmnPurchase = async (cmnData: CmnCheckResponse['data'] | null, selectedNumber: string | null, showAlert: ShowAlert): Promise<void> => {
    if (!purchaseDraft || purchaseDraft.source !== 'cmn' || !cmnData || !selectedNumber) return
    setPurchaseDraft((previous) => (previous ? { ...previous, submitting: true } : null))
    try {
      const url = getApiUrl('/api/cmn/purchase', accountId)
      const data = await apiPostJson<{ status?: string; paymentUrl?: string; message?: string }>(url, { offerId: cmnData.offerId, offerSubType: cmnData.offerSubType, price: cmnData.price, subscriptionId: currentSubId, selectedNumber, paymentType: purchaseDraft.paymentType, txnAmount: purchaseDraft.txnAmount, account_id: accountId })
      if (data.status === 'success' && data.paymentUrl) {
        window.location.href = data.paymentUrl
      } else {
        showAlert(data.message || '提交失败', '失败')
        setPurchaseDraft((previous) => (previous ? { ...previous, submitting: false } : null))
      }
    } catch (error: unknown) {
      showAlert(toUserFacingApiError(error, '网络错误'), '错误')
      setPurchaseDraft((previous) => (previous ? { ...previous, submitting: false } : null))
    }
  }

  return { cart, cartCount, cartQtyDraft, cartTotal, confirmAddToCart, openAddToCart, openPurchaseModal, purchaseDraft, removeCartItem, resetCart: () => setCart([]), setCartQtyDraft, setPurchaseDraft, submitCheckout, submitCmnPurchase, updateCartItem }
}
