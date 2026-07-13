import { describe, expect, it, vi } from 'vitest'

import {
  createPresenceState,
  isRootOpacityTransition,
  presenceReducer,
  subscribeToReducedMotion,
} from './usePresenceValue'

describe('presenceReducer', () => {
  it('starts unmounted when the source value is null', () => {
    const state = createPresenceState<string>(null)

    expect(state).toEqual({ generation: 0, phase: 'unmounted', value: null })
  })

  it('enters immediately when the source value is present', () => {
    const state = createPresenceState('loader')

    expect(state).toEqual({ generation: 1, phase: 'entered', value: 'loader' })
  })

  it('retains the last value while exiting until the matching transition completes', () => {
    const entered = createPresenceState({ quantity: 2 })
    const exiting = presenceReducer(entered, { reducedMotion: false, type: 'source-changed', value: null })
    const completed = presenceReducer(exiting, { generation: exiting.generation, type: 'exit-completed' })

    expect(exiting).toEqual({ generation: 1, phase: 'exiting', value: { quantity: 2 } })
    expect(completed).toEqual({ generation: 1, phase: 'unmounted', value: null })
  })

  it('ignores exit completion while entered', () => {
    const entered = createPresenceState('loader')

    const state = presenceReducer(entered, { generation: entered.generation, type: 'exit-completed' })

    expect(state).toBe(entered)
  })

  it('replaces the retained value when reopened and ignores stale completion', () => {
    const first = createPresenceState('first')
    const exiting = presenceReducer(first, { reducedMotion: false, type: 'source-changed', value: null })
    const reopened = presenceReducer(exiting, { reducedMotion: false, type: 'source-changed', value: 'second' })
    const secondExit = presenceReducer(reopened, { reducedMotion: false, type: 'source-changed', value: null })
    const staleCompletion = presenceReducer(secondExit, { generation: exiting.generation, type: 'exit-completed' })

    expect(reopened).toEqual({ generation: 2, phase: 'entered', value: 'second' })
    expect(staleCompletion).toBe(secondExit)
  })

  it('unmounts immediately when reduced motion is active', () => {
    const entered = createPresenceState('loader')

    const state = presenceReducer(entered, { reducedMotion: true, type: 'source-changed', value: null })

    expect(state).toEqual({ generation: 1, phase: 'unmounted', value: null })
  })
})

describe('isRootOpacityTransition', () => {
  it('accepts only an opacity transition from the root overlay', () => {
    const root = new EventTarget()
    const child = new EventTarget()

    expect(isRootOpacityTransition({ currentTarget: root, propertyName: 'opacity', target: root })).toBe(true)
    expect(isRootOpacityTransition({ currentTarget: root, propertyName: 'transform', target: root })).toBe(false)
    expect(isRootOpacityTransition({ currentTarget: root, propertyName: 'opacity', target: child })).toBe(false)
  })
})

describe('subscribeToReducedMotion', () => {
  it('reports the current preference and removes the registered listener during cleanup', () => {
    const addEventListener = vi.fn()
    const removeEventListener = vi.fn()
    const onChange = vi.fn()
    const mediaQuery: MediaQueryList = {
      addEventListener,
      addListener: vi.fn(),
      dispatchEvent: vi.fn(),
      matches: true,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      removeEventListener,
      removeListener: vi.fn(),
    }

    const cleanup = subscribeToReducedMotion(mediaQuery, onChange)
    cleanup()

    expect(onChange).toHaveBeenCalledWith(true)
    expect(addEventListener).toHaveBeenCalledOnce()
    expect(removeEventListener).toHaveBeenCalledWith('change', addEventListener.mock.calls[0]?.[1])
  })
})
