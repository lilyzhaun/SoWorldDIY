import { describe, expect, it } from 'vitest'

import { getNextDialogFocusIndex } from './useDialogAccessibility'

describe('getNextDialogFocusIndex', () => {
  it('wraps forward focus from the last control to the first', () => {
    expect(getNextDialogFocusIndex(2, 3, false)).toBe(0)
  })

  it('wraps backward focus from the first control to the last', () => {
    expect(getNextDialogFocusIndex(0, 3, true)).toBe(2)
  })

  it('enters the dialog at the correct edge when focus is outside', () => {
    expect(getNextDialogFocusIndex(-1, 3, false)).toBe(0)
    expect(getNextDialogFocusIndex(-1, 3, true)).toBe(2)
  })
})
