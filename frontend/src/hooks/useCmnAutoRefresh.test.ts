import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCmnAutoRefresh } from './useCmnAutoRefresh'

describe('useCmnAutoRefresh', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts auto refresh and records matched result for literal pattern', async () => {
    const requestCmnNumbers = vi.fn(async () => ({
      kind: 'success' as const,
      numbers: ['12345678'],
    }))
    const numbers = {
      canStartAutoRefresh: () => true,
      releaseAutoRequestAfterCancel: vi.fn(),
      requestCmnNumbers,
    }
    const lifecycle = {
      mountedRef: { current: true },
      scopeGenerationRef: { current: 0 },
    }
    const { result } = renderHook(() =>
      useCmnAutoRefresh({
        accountId: 'a1',
        currentSubId: 's1',
        lifecycle,
        numbers,
        visible: true,
      }),
    )

    act(() => {
      result.current.changeCmnPattern('12345678')
    })
    expect(result.current.parsedCmnPattern.kind).toBe('literal')

    act(() => {
      result.current.startCmnAutoRefresh(vi.fn())
    })
    expect(result.current.cmnAutoRefresh.kind).toBe('running')

    await act(async () => {
      await vi.runAllTimersAsync()
    })

    await waitFor(() => {
      expect(result.current.cmnAutoRefresh.kind).toBe('idle')
      expect(result.current.cmnAutoRefresh.message).toContain('找到匹配号码')
    })
    expect(requestCmnNumbers).toHaveBeenCalled()
  })

  it('ignores start when pattern empty/invalid or cannot start', () => {
    const requestCmnNumbers = vi.fn()
    const numbers = {
      canStartAutoRefresh: () => false,
      releaseAutoRequestAfterCancel: vi.fn(),
      requestCmnNumbers,
    }
    const lifecycle = {
      mountedRef: { current: true },
      scopeGenerationRef: { current: 0 },
    }
    const { result } = renderHook(() =>
      useCmnAutoRefresh({
        accountId: 'a1',
        currentSubId: 's1',
        lifecycle,
        numbers,
        visible: true,
      }),
    )

    act(() => {
      result.current.startCmnAutoRefresh(vi.fn())
    })
    expect(requestCmnNumbers).not.toHaveBeenCalled()

    // re-enable canStart but invalid pattern
    numbers.canStartAutoRefresh = () => true
    act(() => {
      result.current.changeCmnPattern('!!!')
    })
    act(() => {
      result.current.startCmnAutoRefresh(vi.fn())
    })
    expect(requestCmnNumbers).not.toHaveBeenCalled()
  })

  it('cancels running search with announce message', async () => {
    const requestCmnNumbers = vi.fn(
      () =>
        new Promise<{ kind: 'success'; numbers: string[] }>(() => {
          /* hang */
        }),
    )
    const numbers = {
      canStartAutoRefresh: () => true,
      releaseAutoRequestAfterCancel: vi.fn(),
      requestCmnNumbers,
    }
    const lifecycle = {
      mountedRef: { current: true },
      scopeGenerationRef: { current: 0 },
    }
    const { result } = renderHook(() =>
      useCmnAutoRefresh({
        accountId: 'a1',
        currentSubId: 's1',
        lifecycle,
        numbers,
        visible: true,
      }),
    )

    act(() => {
      result.current.changeCmnPattern('12345678')
    })
    act(() => {
      result.current.startCmnAutoRefresh(vi.fn())
    })
    expect(result.current.cmnAutoRefresh.kind).toBe('running')

    act(() => {
      result.current.cancelCmnAutoRefresh(true)
    })
    expect(result.current.cmnAutoRefresh.kind).toBe('idle')
    expect(result.current.cmnAutoRefresh.message).toBe('已取消自动查找')
    expect(numbers.releaseAutoRequestAfterCancel).toHaveBeenCalled()
  })
})
