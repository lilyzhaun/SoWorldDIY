import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const numbers = vi.hoisted(() => ({
  canStartAutoRefresh: vi.fn(() => true),
  cmnCanRefresh: true,
  cmnCooldown: 0,
  cmnNumbers: ['123'],
  cmnNumbersLoading: false,
  refreshCmnNumbers: vi.fn(),
  releaseAutoRequestAfterCancel: vi.fn(),
  requestCmnNumbers: vi.fn(),
  selectedNumber: null as string | null,
  setSelectedNumber: vi.fn(),
}))

const autoRefresh = vi.hoisted(() => ({
  cancelCmnAutoRefresh: vi.fn(),
  changeCmnPattern: vi.fn(),
  cmnAutoRefresh: { kind: 'idle' as const, message: '' },
  cmnPattern: '',
  parsedCmnPattern: { kind: 'empty' as const },
  startCmnAutoRefresh: vi.fn(),
}))

const eligibility = vi.hoisted(() => ({
  checkCmnEligibility: vi.fn(),
  cmnData: null as null | { price: number },
  cmnError: null as string | null,
  cmnLoading: false,
}))

vi.mock('./useCmnNumbers', () => ({
  CMN_REFRESH_COOLDOWN_SECONDS: 3,
  useCmnNumbers: () => numbers,
}))
vi.mock('./useCmnAutoRefresh', () => ({
  useCmnAutoRefresh: () => autoRefresh,
  cmnAutoRefreshResultMessage: () => '',
}))
vi.mock('./useCmnEligibility', () => ({
  useCmnEligibility: () => eligibility,
}))

import { useCmn } from './useCmn'

describe('useCmn submitChangeNumber', () => {
  beforeEach(() => {
    numbers.selectedNumber = null
    eligibility.cmnData = null
  })

  it('alerts when no number selected', () => {
    const { result } = renderHook(() => useCmn('a1', 's1', true))
    const showAlert = vi.fn()
    const openPurchase = vi.fn()
    act(() => {
      result.current.submitChangeNumber(showAlert, openPurchase)
    })
    expect(showAlert).toHaveBeenCalledWith('请先选择号码', '提示')
    expect(openPurchase).not.toHaveBeenCalled()
  })

  it('returns early when eligibility data missing', () => {
    numbers.selectedNumber = '999'
    const { result } = renderHook(() => useCmn('a1', 's1', true))
    const showAlert = vi.fn()
    const openPurchase = vi.fn()
    act(() => {
      result.current.submitChangeNumber(showAlert, openPurchase)
    })
    expect(openPurchase).not.toHaveBeenCalled()
  })

  it('opens purchase when number and data present', () => {
    numbers.selectedNumber = '888'
    eligibility.cmnData = { price: 12 }
    const { result } = renderHook(() => useCmn('a1', 's1', true))
    const showAlert = vi.fn()
    const openPurchase = vi.fn()
    act(() => {
      result.current.submitChangeNumber(showAlert, openPurchase)
    })
    expect(openPurchase).toHaveBeenCalledWith('更换号码: 888', 12, 'cmn')
  })
})
