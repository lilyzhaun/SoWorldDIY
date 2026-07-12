import { describe, expect, it } from 'vitest'

import { CMN_REFRESH_COOLDOWN_SECONDS } from './useCmn'

describe('useCmn refresh contract', () => {
  it('uses an exact three-second cooldown after a successful refresh', () => {
    expect(CMN_REFRESH_COOLDOWN_SECONDS).toBe(3)
  })
})
