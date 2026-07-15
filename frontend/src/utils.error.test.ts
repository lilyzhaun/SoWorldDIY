import { describe, expect, it } from 'vitest'

import { ApiHttpError } from '@/api/client'
import { toErrorMessage, toUserFacingApiError } from '@/utils'

describe('toUserFacingApiError', () => {
  it('prefers body message/detail from ApiHttpError', () => {
    expect(
      toUserFacingApiError(
        new ApiHttpError(400, 'Bad', '{"message":"bad req"}', { message: 'bad req' }),
        'fallback',
      ),
    ).toBe('bad req')
    expect(
      toUserFacingApiError(
        new ApiHttpError(400, 'Bad', '{"detail":"d"}', { detail: 'd' }),
        'fallback',
      ),
    ).toBe('d')
  })

  it('maps known status codes when body has no message', () => {
    expect(toUserFacingApiError(new ApiHttpError(401, 'Unauthorized'), 'fb')).toBe(
      '登录已失效，请重新登录',
    )
    expect(toUserFacingApiError(new ApiHttpError(403, 'Forbidden'), 'fb')).toBe(
      '没有权限执行此操作',
    )
    expect(toUserFacingApiError(new ApiHttpError(404, 'Missing'), 'fb')).toBe(
      '请求的资源不存在',
    )
    expect(toUserFacingApiError(new ApiHttpError(429, 'Too Many'), 'fb')).toBe(
      '请求过于频繁，请稍后再试',
    )
    expect(toUserFacingApiError(new ApiHttpError(503, 'Down'), 'fb')).toBe(
      '服务暂时不可用，请稍后再试',
    )
    expect(toUserFacingApiError(new ApiHttpError(418, "I'm a teapot"), 'fb')).toBe('fb')
  })

  it('falls back for generic errors', () => {
    expect(toUserFacingApiError(new Error('network'), 'fb')).toBe('network')
    expect(toUserFacingApiError('x', 'fb')).toBe('fb')
  })
})

describe('toErrorMessage', () => {
  it('stringifies unknown errors', () => {
    expect(toErrorMessage(new Error('e'))).toBe('e')
    expect(toErrorMessage('plain')).toBe('plain')
  })
})
