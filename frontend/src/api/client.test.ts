import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiHttpError, apiFetch, apiGet, apiPostJson, getCookie, withCsrfHeaders } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api client helpers', () => {
  it('reads cookies by name', () => {
    expect(getCookie('csrf_token', 'foo=bar; csrf_token=abc%20123')).toBe('abc 123')
    expect(getCookie('csrf', 'csrf_token=wrong; csrf=right')).toBe('right')
    expect(getCookie('missing', 'foo=bar')).toBe('')
  })

  it('adds csrf header when token exists', () => {
    const headers = withCsrfHeaders({ 'Content-Type': 'application/json' }, 'csrf_token=token')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('x-csrf-token')).toBe('token')
  })

  it('does not add an empty csrf header', () => {
    const headers = withCsrfHeaders({ Accept: 'application/json' }, 'foo=bar')

    expect(headers.get('Accept')).toBe('application/json')
    expect(headers.has('x-csrf-token')).toBe(false)
  })

  it.each(['GET', 'HEAD'])('preserves safe %s requests without csrf injection', async (method) => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/profile', { method, headers: { Accept: 'application/json' } })

    expect(fetchMock).toHaveBeenCalledOnce()
    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe(method)
    expect(init?.headers).toEqual({ Accept: 'application/json' })
  })

  it('adds csrf protection to mutation requests and preserves existing headers', async () => {
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: { cookie: 'csrf_token=secure%20token' },
    })
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/profile', { method: 'PATCH', headers: { 'X-Request-ID': 'request-7' } })

    const headers = fetchMock.mock.calls[0]?.[1]?.headers
    expect(headers).toBeInstanceOf(Headers)
    expect(new Headers(headers).get('x-request-id')).toBe('request-7')
    expect(new Headers(headers).get('x-csrf-token')).toBe('secure token')
  })

  it('returns parsed JSON from GET requests', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ status: 'success', balance: '8.0' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiGet<{ status: string; balance: string }>('/api/balance')).resolves.toEqual({ status: 'success', balance: '8.0' })
  })

  it('forwards AbortSignal through init', async () => {
    const controller = new AbortController()
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiGet('/api/balance', { signal: controller.signal })

    expect(fetchMock.mock.calls[0]?.[1]?.signal).toBe(controller.signal)
  })

  it('throws ApiHttpError with status and body on non-OK GET', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () =>
      new Response(JSON.stringify({ message: 'nope' }), { status: 403, statusText: 'Forbidden' }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiGet('/api/balance')).rejects.toBeInstanceOf(ApiHttpError)
    await expect(apiGet('/api/balance')).rejects.toMatchObject({
      name: 'ApiHttpError',
      status: 403,
      statusText: 'Forbidden',
      bodyJson: { message: 'nope' },
    })
  })

  it('throws ApiHttpError with plain body text when JSON parse fails', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response('gateway down', { status: 502, statusText: 'Bad Gateway' }))
    vi.stubGlobal('fetch', fetchMock)

    try {
      await apiPostJson('/api/purchase', { items: [] })
      expect.unreachable('expected ApiHttpError')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiHttpError)
      const httpError = error as ApiHttpError
      expect(httpError.status).toBe(502)
      expect(httpError.bodyText).toBe('gateway down')
      expect(httpError.bodyJson).toBeUndefined()
    }
  })

  it('serializes JSON keys in insertion order and enforces the content type', async () => {
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: { cookie: 'csrf_token=token' },
    })
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ status: 'success' }))
    vi.stubGlobal('fetch', fetchMock)

    await apiPostJson('/api/purchase', { items: [], subscriptionId: 'sub-1', price: 10 })

    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe('{"items":[],"subscriptionId":"sub-1","price":10}')
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json')
    expect(new Headers(init?.headers).get('x-csrf-token')).toBe('token')
  })
})
