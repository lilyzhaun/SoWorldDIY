import { afterEach, describe, expect, it, vi } from 'vitest'

import { performLogout } from './useLogout'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubCookie(): void {
  Object.defineProperty(globalThis, 'document', {
    configurable: true,
    value: { cookie: 'csrf_token=tok' },
  })
}

describe('performLogout', () => {
  it('navigates on 2xx success', async () => {
    const navigate = vi.fn()
    const showAlert = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        redirected: true,
        url: 'http://localhost/main/other',
        status: 200,
        text: async () => '',
        json: async () => ({}),
      }),
    )
    stubCookie()

    await performLogout('account-1', showAlert, navigate)

    expect(navigate).toHaveBeenCalledWith('http://localhost/main/other')
    expect(showAlert).not.toHaveBeenCalled()
  })

  it('shows JSON message and does not navigate on 403', async () => {
    const navigate = vi.fn()
    const showAlert = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        redirected: false,
        url: 'http://localhost/logout',
        text: async () => JSON.stringify({ status: 'error', message: 'CSRF token invalid', code: 'csrf_invalid' }),
        json: async () => ({ status: 'error', message: 'CSRF token invalid', code: 'csrf_invalid' }),
      }),
    )
    stubCookie()

    await performLogout('account-1', showAlert, navigate)

    expect(navigate).not.toHaveBeenCalled()
    expect(showAlert).toHaveBeenCalledWith('CSRF token invalid', '错误')
  })

  it('shows status fallback and does not navigate on non-JSON 403 body', async () => {
    const navigate = vi.fn()
    const showAlert = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        redirected: false,
        url: 'http://localhost/logout',
        text: async () => '<html>forbidden</html>',
        json: async () => {
          throw new SyntaxError('Unexpected token')
        },
      }),
    )
    stubCookie()

    await performLogout('account-1', showAlert, navigate)

    expect(navigate).not.toHaveBeenCalled()
    expect(showAlert).toHaveBeenCalledWith('没有权限执行此操作', '错误')
  })

  it('shows status fallback and does not navigate on non-JSON 503 body', async () => {
    const navigate = vi.fn()
    const showAlert = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        redirected: false,
        url: 'http://localhost/logout',
        text: async () => 'gateway timeout plain text',
        json: async () => {
          throw new SyntaxError('Unexpected token')
        },
      }),
    )
    stubCookie()

    await performLogout('account-1', showAlert, navigate)

    expect(navigate).not.toHaveBeenCalled()
    expect(showAlert).toHaveBeenCalledWith('服务暂时不可用，请稍后再试', '错误')
  })

  it('shows alert and does not navigate on network failure', async () => {
    const navigate = vi.fn()
    const showAlert = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))
    stubCookie()

    await performLogout('account-1', showAlert, navigate)

    expect(navigate).not.toHaveBeenCalled()
    expect(showAlert).toHaveBeenCalledWith('network down', '错误')
  })
})
