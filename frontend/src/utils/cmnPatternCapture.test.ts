import { describe, expect, it } from 'vitest'

import { parseBackreference, validateCapture } from './cmnPatternCapture'

describe('parseBackreference', () => {
  it('parses valid backreferences \\1-\\4', () => {
    expect(parseBackreference('\\1abc', 0)).toBe(2)
    expect(parseBackreference('x\\4', 1)).toBe(3)
  })

  it('rejects invalid backreferences', () => {
    expect(parseBackreference('1abc', 0)).toBeNull()
    expect(parseBackreference('\\5', 0)).toBeNull()
    expect(parseBackreference('\\10', 0)).toBeNull()
    expect(parseBackreference('\\', 0)).toBeNull()
  })
})

describe('validateCapture', () => {
  it('accepts simple digit capture groups', () => {
    const source = '(\\d{2})'
    const result = validateCapture(source, 0, 0, 0)
    expect(result).not.toBeNull()
    expect(result?.openGroups).toBe(1)
  })

  it('rejects nested groups and invalid bodies', () => {
    expect(validateCapture('((\\d))', 0, 0, 0)).toBeNull()
    expect(validateCapture('(?x)', 0, 0, 0)).toBeNull()
    expect(validateCapture('(', 0, 0, 0)).toBeNull()
    expect(validateCapture('(\\d)', 0, 4, 0)).toBeNull()
  })
})
