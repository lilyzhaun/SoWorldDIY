import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useBodyScrollLock } from './useBodyScrollLock'

describe('useBodyScrollLock', () => {
  afterEach(() => {
    document.body.classList.remove('no-scroll')
    vi.restoreAllMocks()
  })

  it('toggles no-scroll on non-desktop when lock is true', () => {
    vi.spyOn(window, 'matchMedia').mockReturnValue({
      matches: false,
      media: '',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    } as MediaQueryList)

    const { unmount, rerender } = renderHook(({ lock }) => useBodyScrollLock(lock), {
      initialProps: { lock: true },
    })
    expect(document.body.classList.contains('no-scroll')).toBe(true)

    rerender({ lock: false })
    expect(document.body.classList.contains('no-scroll')).toBe(false)

    unmount()
    expect(document.body.classList.contains('no-scroll')).toBe(false)
  })

  it('removes no-scroll on desktop landscape regardless of lock', () => {
    vi.spyOn(window, 'matchMedia').mockReturnValue({
      matches: true,
      media: '',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    } as MediaQueryList)

    document.body.classList.add('no-scroll')
    renderHook(() => useBodyScrollLock(true))
    expect(document.body.classList.contains('no-scroll')).toBe(false)
  })
})
