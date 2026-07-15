import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useAppModal } from './useAppModal'

describe('useAppModal', () => {
  it('shows alert modal with optional tone and closes with callback', () => {
    const onAfterClose = vi.fn()
    const { result } = renderHook(() => useAppModal({ onAfterClose }))

    act(() => {
      result.current.showAlert('hello', '标题', 'error')
    })
    expect(result.current.showModal).toBe(true)
    expect(result.current.modalKind).toBe('alert')
    expect(result.current.modalTitle).toBe('标题')
    expect(result.current.alert).toEqual({ text: 'hello', tone: 'error' })

    act(() => {
      result.current.closeCustomModal()
    })
    expect(result.current.showModal).toBe(false)
    expect(onAfterClose).toHaveBeenCalled()
  })

  it('opens switch and cart modals with correct modes', () => {
    const { result } = renderHook(() => useAppModal())

    act(() => {
      result.current.openSwitchModal()
    })
    expect(result.current.modalKind).toBe('switch')
    expect(result.current.modalMode).toBe('bottom-sheet')

    act(() => {
      result.current.openCartModal(0)
    })
    // empty cart does not open
    expect(result.current.modalKind).toBe('switch')

    act(() => {
      result.current.openCartModal(2)
    })
    expect(result.current.modalKind).toBe('cart')
    expect(result.current.modalTitle).toBe('购物车')

    act(() => {
      result.current.openKind('purchase', '确认购买', 'center')
    })
    expect(result.current.modalKind).toBe('purchase')
    expect(result.current.modalTitle).toBe('确认购买')
  })

  it('shows alert without tone when omitted', () => {
    const { result } = renderHook(() => useAppModal())
    act(() => {
      result.current.showAlert('plain')
    })
    expect(result.current.alert).toEqual({ text: 'plain' })
    expect(result.current.modalTitle).toBe('提示')
  })
})
