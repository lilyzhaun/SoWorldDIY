import { act, cleanup, render, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { usePurchaseCart } from '@/hooks/usePurchaseCart'
import { PurchaseModalContent } from './PurchaseModalContent'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('shows the same full price that a new-line purchase submits', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'error' }) })
  vi.stubGlobal('fetch', fetch)
  const { result } = renderHook(() => usePurchaseCart('acc', 's1', '50'))
  act(() => result.current.openPurchaseModal('order', 50, 'cart', vi.fn()))
  act(() => result.current.setPurchaseDraft((previous) => (previous ? { ...previous, newLine: true } : null)))
  const draft = result.current.purchaseDraft!
  const view = render(<PurchaseModalContent balance="50" draft={draft} onChangeDraft={vi.fn()} showNewLineOption />)
  expect(view.getByText('$50.0')).toBeTruthy()
  expect((view.getByRole('spinbutton') as HTMLInputElement).disabled).toBe(true)
  await act(async () => {
    await result.current.submitCheckout(vi.fn())
  })
  const body = JSON.parse(fetch.mock.calls[0][1].body)
  expect(body.price - body.txnAmount).toBe(50)
  expect(body.txnAmount).toBe(0)
})
