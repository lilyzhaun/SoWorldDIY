import { describe, expect, it } from 'vitest'

import { PROFILE_REFRESH_COMPLETION_DELAY_MS } from './useProfileRefresh'

describe('useProfileRefresh timing contract', () => {
  it('keeps the refreshing indicator active for the existing 500ms completion delay', () => {
    expect(PROFILE_REFRESH_COMPLETION_DELAY_MS).toBe(500)
  })
})
