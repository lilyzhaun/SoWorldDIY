import { describe, expect, it } from 'vitest'

import { nextAllTabState } from './switchCategory'

describe('nextAllTabState', () => {
  it('increments click count until free-plan reveal threshold', () => {
    let state = { allTabClickCount: 0, showFreePlans: false }
    for (let i = 1; i <= 4; i += 1) {
      const next = nextAllTabState(state)
      expect(next).toEqual({
        allTabClickCount: i,
        showFreePlans: false,
        revealFreePlans: false,
      })
      state = { allTabClickCount: next.allTabClickCount, showFreePlans: next.showFreePlans }
    }
    const reveal = nextAllTabState(state)
    expect(reveal).toEqual({ allTabClickCount: 0, showFreePlans: true, revealFreePlans: true })
  })

  it('does not re-reveal when free plans already shown', () => {
    const next = nextAllTabState({ allTabClickCount: 10, showFreePlans: true })
    expect(next.revealFreePlans).toBe(false)
    expect(next.showFreePlans).toBe(true)
    expect(next.allTabClickCount).toBe(11)
  })
})
