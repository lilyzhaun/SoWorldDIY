import { describe, expect, it } from 'vitest'

import { findCmnPatternRanges, parseCmnPattern, segmentCmnCandidate } from './cmnPattern'

describe('parseCmnPattern', () => {
  it('returns empty when the input is empty', () => {
    expect(parseCmnPattern('')).toEqual({ kind: 'empty' })
  })

  it('treats digits-only input as a literal substring', () => {
    expect(parseCmnPattern('666')).toEqual({ kind: 'literal', value: '666' })
  })

  it.each(['6[0-9]{2}', '^6\\d{7}$', '666|888'])('accepts the safe regex pattern %s', (source) => {
    const parsed = parseCmnPattern(source)

    expect(parsed.kind).toBe('regex')
  })

  it.each([
    '[',
    '(\\d+)+',
    '\\d*',
    '123456789012345678901234567890123',
    '<img src=x onerror=alert(1)>',
    '6{2,1}',
    '[9-0]',
    '6++',
    '6||8',
    '(?=6)',
    '\\1',
    '\\p{N}',
    '/6/g',
    '1|2|3|4|5',
    '.........',
    '6{0}',
  ])('rejects the invalid or unsafe pattern %s', (source) => {
    const parsed = parseCmnPattern(source)

    expect(parsed.kind).toBe('invalid')
  })
})

describe('findCmnPatternRanges', () => {
  it('finds every non-overlapping literal match', () => {
    expect(findCmnPatternRanges('66666666', '66')).toEqual([
      { start: 0, end: 2 },
      { start: 2, end: 4 },
      { start: 4, end: 6 },
      { start: 6, end: 8 },
    ])
  })

  it('finds multiple safe regex matches without retaining global state', () => {
    expect(findCmnPatternRanges('66126634', '6[0-9]')).toEqual([
      { start: 0, end: 2 },
      { start: 4, end: 6 },
    ])
    expect(findCmnPatternRanges('66126634', '6[0-9]')).toEqual([
      { start: 0, end: 2 },
      { start: 4, end: 6 },
    ])
  })

  it('applies anchors and alternatives to the complete candidate', () => {
    const pattern = '^666\\d{5}$|^888\\d{5}$'

    expect(findCmnPatternRanges('66612345', pattern)).toEqual([{ start: 0, end: 8 }])
    expect(findCmnPatternRanges('88812345', pattern)).toEqual([{ start: 0, end: 8 }])
    expect(findCmnPatternRanges('16661234', pattern)).toEqual([])
  })

  it('does not evaluate candidates that are not exactly eight ASCII digits', () => {
    expect(findCmnPatternRanges('6666666', '6')).toEqual([])
    expect(findCmnPatternRanges('6666666a', '6')).toEqual([])
    expect(findCmnPatternRanges('６６６６６６６６', '6')).toEqual([])
  })

  it.each(['(\\d+)+', '', '<img src=x onerror=alert(1)>', '['])('returns no ranges and does not throw for unsafe raw input %s', (pattern) => {
    expect(() => findCmnPatternRanges('66666666', pattern)).not.toThrow()
    expect(findCmnPatternRanges('66666666', pattern)).toEqual([])
  })
})

describe('segmentCmnCandidate', () => {
  it('preserves the exact candidate text while marking matched fragments', () => {
    const candidate = '66126634'
    const segments = segmentCmnCandidate(candidate, findCmnPatternRanges(candidate, '6[0-9]'))

    expect(segments.map((segment) => segment.text).join('')).toBe(candidate)
    expect(segments.filter((segment) => segment.highlighted).map((segment) => segment.text)).toEqual(['66', '66'])
  })
})
