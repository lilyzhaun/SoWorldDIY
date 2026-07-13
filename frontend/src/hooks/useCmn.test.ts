import { describe, expect, it } from 'vitest'

import { cmnAutoRefreshResultMessage } from './useCmnAutoRefresh'
import { CMN_REFRESH_COOLDOWN_SECONDS } from './useCmn'

describe('useCmn refresh contract', () => {
  it('uses an exact three-second cooldown after a successful refresh', () => {
    expect(CMN_REFRESH_COOLDOWN_SECONDS).toBe(3)
  })
})

describe('CMN auto-refresh result messages', () => {
  it.each([
    [{ kind: 'matched', attempts: 2 } as const, '已在第 2 次查找中找到匹配号码'],
    [{ kind: 'exhausted', attempts: 20 } as const, '已完成 20 次查找，未找到匹配号码'],
    [{ kind: 'aborted', attempts: 1 } as const, '已取消自动查找'],
    [{ kind: 'unavailable', attempts: 1 } as const, '自动查找当前不可用'],
    [{ kind: 'error', attempts: 1 } as const, '自动查找因请求失败而停止'],
  ])('preserves the message for %s', (result, expected) => {
    expect(cmnAutoRefreshResultMessage(result)).toBe(expected)
  })
})
