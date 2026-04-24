import { describe, expect, it } from 'vitest'

import { getCookie, withCsrfHeaders } from './client'

describe('api client helpers', () => {
  it('reads cookies by name', () => {
    expect(getCookie('csrf_token', 'foo=bar; csrf_token=abc%20123')).toBe('abc 123')
    expect(getCookie('missing', 'foo=bar')).toBe('')
  })

  it('adds csrf header when token exists', () => {
    const headers = withCsrfHeaders({ 'Content-Type': 'application/json' }, 'csrf_token=token')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('x-csrf-token')).toBe('token')
  })
})
