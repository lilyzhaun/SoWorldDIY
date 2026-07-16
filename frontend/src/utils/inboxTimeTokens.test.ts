import { describe, expect, it } from 'vitest'

import { splitInboxTimeTokens } from './inboxTimeTokens'

describe('splitInboxTimeTokens', () => {
  it('returns plain text when no time tokens exist', () => {
    expect(splitInboxTimeTokens('hello world')).toEqual([{ text: 'hello world', nowrap: false }])
  })

  it('splits Chinese time tokens as nowrap segments', () => {
    expect(splitInboxTimeTokens('剩餘3小時後到期')).toEqual([
      { text: '剩餘', nowrap: false },
      { text: '3小時', nowrap: true },
      { text: '後到期', nowrap: false },
    ])
    expect(splitInboxTimeTokens('10分鐘')).toEqual([{ text: '10分鐘', nowrap: true }])
    expect(splitInboxTimeTokens('2天1個月')).toEqual([
      { text: '2天', nowrap: true },
      { text: '1個月', nowrap: true },
    ])
  })
})
