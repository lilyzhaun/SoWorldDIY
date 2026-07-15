import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useTransfer } from './useTransfer'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useTransfer', () => {
  it('validates target and amount before submit', async () => {
    const { result } = renderHook(() => useTransfer('acc', 'sub1'))
    act(() => {
      result.current.openTransferModal(
        { stopPropagation() {} } as React.MouseEvent,
        {
          minTransfer: 1,
          maxValue: 10,
          userOfferId: 'u',
          balanceResourceId: 'b',
          unit: 'MB',
          productFamily: 'DATA',
        } as never,
        () => {},
      )
    })
    await act(async () => {
      const out = await result.current.submitTransfer({
        subscriptionId: 'sub1',
        mobile: '51234567',
      })
      expect(out).toBeNull()
    })
    expect(result.current.transferError).toContain('手机号码')

    act(() => {
      result.current.setTransferTarget('51234567')
      result.current.setTransferAmount('bad')
    })
    await act(async () => {
      await result.current.submitTransfer({ subscriptionId: 'sub1', mobile: '51234567' })
    })
    expect(result.current.transferError).toContain('转移数量')
  })

  it('submits transfer successfully', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => JSON.stringify({ status: 'success' }),
        json: async () => ({ status: 'success' }),
      }),
    )
    document.cookie = 'csrf_token=tok'
    const { result } = renderHook(() => useTransfer('acc', 'sub1'))
    act(() => {
      result.current.openTransferModal(
        { stopPropagation() {} } as React.MouseEvent,
        {
          minTransfer: 1,
          maxValue: 10,
          userOfferId: 'u',
          balanceResourceId: 'b',
          unit: 'MB',
          productFamily: 'DATA',
        } as never,
        () => {},
      )
      result.current.setTransferTarget('51234567')
      result.current.setTransferAmount('2')
    })
    let target: string | null = null
    await act(async () => {
      target = await result.current.submitTransfer({
        subscriptionId: 'sub1',
        mobile: '51234567',
      })
    })
    expect(target).toBe('51234567')
  })

  it('handles API failure message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => JSON.stringify({ status: 'error', message: 'fail x' }),
        json: async () => ({ status: 'error', message: 'fail x' }),
      }),
    )
    document.cookie = 'csrf_token=tok'
    const { result } = renderHook(() => useTransfer('acc', 'sub1'))
    act(() => {
      result.current.openTransferModal(
        { stopPropagation() {} } as React.MouseEvent,
        {
          minTransfer: 1,
          maxValue: 10,
          userOfferId: 'u',
          balanceResourceId: 'b',
          unit: 'MB',
          productFamily: 'DATA',
        } as never,
        () => {},
      )
      result.current.setTransferTarget('51234567')
      result.current.setTransferAmount('2')
    })
    await act(async () => {
      await result.current.submitTransfer({ subscriptionId: 'sub1', mobile: '51234567' })
    })
    expect(result.current.transferError).toBe('fail x')
    act(() => {
      result.current.resetTransfer()
    })
    expect(result.current.transferError).toBe('')
  })
})
