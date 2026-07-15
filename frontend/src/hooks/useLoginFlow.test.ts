import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LOGIN_REDIRECT_DELAY_MS, useLoginFlow } from './useLoginFlow'

const apiFetch = vi.hoisted(() => vi.fn())
const apiPostJson = vi.hoisted(() => vi.fn())
vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiFetch, apiPostJson }
})

describe('useLoginFlow', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    apiPostJson.mockReset()
    vi.useFakeTimers({ shouldAdvanceTime: true })
    window.history.replaceState({}, '', '/login')
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('detects add mode from query string', () => {
    window.history.replaceState({}, '', '/login?add=1')
    const { result } = renderHook(() => useLoginFlow())
    expect(result.current.isAddMode).toBe(true)
  })

  it('validates OTP send inputs and success countdown', async () => {
    const { result } = renderHook(() => useLoginFlow())

    await act(async () => {
      await result.current.handleSendOtp()
    })
    expect(result.current.toast?.message).toBe('请先输入账号')

    act(() => {
      result.current.setIdentifier('user@example.com')
    })
    await act(async () => {
      await result.current.handleSendOtp()
    })
    expect(result.current.toast?.message).toBe('请先输入鉴权码')

    act(() => {
      result.current.setAuthCode('code')
    })
    apiPostJson.mockResolvedValueOnce({ status: 'success' })
    await act(async () => {
      await result.current.handleSendOtp()
    })
    expect(result.current.toast?.message).toBe('验证码已发送')
    expect(result.current.otpBusy).toBe(true)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(61_000)
    })
    expect(result.current.otpBusy).toBe(false)
    expect(result.current.otpLabel).toBe('获取验证码')
  })

  it('handles OTP send failure', async () => {
    const { result } = renderHook(() => useLoginFlow())
    act(() => {
      result.current.setIdentifier('u')
      result.current.setAuthCode('c')
    })
    apiPostJson.mockResolvedValueOnce({ status: 'fail', message: '发送失败' })
    await act(async () => {
      await result.current.handleSendOtp()
    })
    expect(result.current.toast?.tone).toBe('error')
    expect(result.current.otpBusy).toBe(false)
  })

  it('submits password login and redirects', async () => {
    const { result } = renderHook(() => useLoginFlow())
    const assign = vi.fn()
    // jsdom location.href assignment
    const original = window.location
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...original, href: '', assign },
    })

    act(() => {
      result.current.setIdentifier('u')
      result.current.setPassword('p')
      result.current.setAuthCode('c')
    })
    apiFetch.mockResolvedValueOnce({
      status: 200,
      json: async () => ({ status: 'success', redirect: '/main' }),
    })

    await act(async () => {
      await result.current.handleSubmit({
        preventDefault() {},
      } as React.FormEvent<HTMLFormElement>)
    })
    expect(result.current.loginSucceeded).toBe(true)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LOGIN_REDIRECT_DELAY_MS)
    })
    expect(window.location.href).toBe('/main')

    Object.defineProperty(window, 'location', { configurable: true, value: original })
  })

  it('handles 401 and non-success login responses', async () => {
    const { result } = renderHook(() => useLoginFlow())
    act(() => {
      result.current.setTab('otp')
      result.current.setIdentifier('u')
      result.current.setOtp('123456')
      result.current.setAuthCode('c')
    })

    apiFetch.mockResolvedValueOnce({
      status: 401,
      json: async () => ({ message: '鉴权失败' }),
    })
    await act(async () => {
      await result.current.handleSubmit({ preventDefault() {} } as React.FormEvent<HTMLFormElement>)
    })
    expect(result.current.toast?.message).toBe('鉴权失败')
    expect(result.current.submitBusy).toBe(false)

    apiFetch.mockResolvedValueOnce({
      status: 200,
      json: async () => ({ status: 'fail', message: '登录失败了' }),
    })
    await act(async () => {
      await result.current.handleSubmit({ preventDefault() {} } as React.FormEvent<HTMLFormElement>)
    })
    expect(result.current.toast?.message).toBe('登录失败了')
  })

  it('clears retained toast on opacity transition end', () => {
    const { result } = renderHook(() => useLoginFlow())
    act(() => {
      result.current.setIdentifier('x')
    })
    // force retained toast via send otp validation
    act(() => {
      void result.current.handleSendOtp()
    })
    // toast present; clear visible toast timer
    act(() => {
      vi.advanceTimersByTime(3000)
    })
    act(() => {
      result.current.clearRetainedToastIfHidden('opacity')
    })
    expect(result.current.retainedToast).toBeNull()
  })
})
