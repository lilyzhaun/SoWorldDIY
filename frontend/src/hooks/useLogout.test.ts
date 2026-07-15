import { afterEach, describe, expect, it, vi } from 'vitest'

import { performLogout } from './useLogout'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('performLogout', () => {
  it('navigates on 2xx success', async () => {
    const navigate = vi.fn()
    const showAlert = vi.fn()
    const response = {
      ok: true,
      redirected: true,
      url: 'http://localhost/main/other',
      status: 200,
      json: async () => ({}),
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: { cookie: 'csrf_token=tok' },
    })

    await performLogout('account-1', showAlert, navigate)

    expect(navigate).toHaveBeenCalledWith('http://localhost/main/other')
    expect(showAlert).not.toHaveBeenCalled()
  })

  it('shows alert and does not navigate on 403', async () => {
    const navigate = vi.fn()
    const showAlert = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        redirected: false,
        url: 'http://localhost/logout',
        json: async () => ({ status: 'error', message: 'CSRF token invalid', code: 'csrf_invalid' }),
      }),
    )
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: { cookie: 'csrf_token=tok' },
    })

    await performLogout('account-1', showAlert, navigate)

    expect(navigate).not.toHaveBeenCalled()
    expect(showAlert).toHaveBeenCalledWith('CSRF token invalid', '错误')
  })

  it('shows alert and does not navigate on network failure', async () => {
    const navigate = vi.fn()
    const showAlert = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: { cookie: 'csrf_token=tok' },
    })

    await performLogout('account-1', showAlert, navigate)

    expect(navigate).not.toHaveBeenCalled()
    expect(showAlert).toHaveBeenCalledWith('network down', '错误')
  })
})
