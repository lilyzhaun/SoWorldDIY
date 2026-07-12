import { useCallback, useEffect, useReducer, useState } from 'react'

export type PresencePhase = 'unmounted' | 'entered' | 'exiting'

export type PresenceState<T> =
  | { readonly generation: number; readonly phase: 'unmounted'; readonly value: null }
  | { readonly generation: number; readonly phase: 'entered' | 'exiting'; readonly value: T }

type PresenceAction<T> =
  | { readonly reducedMotion: boolean; readonly type: 'source-changed'; readonly value: T | null }
  | { readonly generation: number; readonly type: 'exit-completed' }

export type PresenceValue<T> = PresenceState<T> & { readonly completeExit: () => void }

type TransitionCompletionEvent = {
  readonly currentTarget: EventTarget
  readonly propertyName: string
  readonly target: EventTarget
}

export function isRootOpacityTransition(event: TransitionCompletionEvent): boolean {
  return event.target === event.currentTarget && event.propertyName === 'opacity'
}

export function subscribeToReducedMotion(mediaQuery: MediaQueryList, onChange: (matches: boolean) => void): () => void {
  const handleChange = (event: MediaQueryListEvent): void => onChange(event.matches)
  onChange(mediaQuery.matches)
  mediaQuery.addEventListener('change', handleChange)
  return () => mediaQuery.removeEventListener('change', handleChange)
}

export function createPresenceState<T>(value: T | null): PresenceState<T> {
  return value === null
    ? { generation: 0, phase: 'unmounted', value: null }
    : { generation: 1, phase: 'entered', value }
}

export function presenceReducer<T>(state: PresenceState<T>, action: PresenceAction<T>): PresenceState<T> {
  switch (action.type) {
    case 'source-changed':
      if (action.value !== null) {
        return { generation: state.generation + 1, phase: 'entered', value: action.value }
      }
      if (state.phase === 'unmounted') return state
      return action.reducedMotion
        ? { generation: state.generation, phase: 'unmounted', value: null }
        : { generation: state.generation, phase: 'exiting', value: state.value }
    case 'exit-completed':
      if (state.phase !== 'exiting' || action.generation !== state.generation) return state
      return { generation: state.generation, phase: 'unmounted', value: null }
  }
}

export function usePresenceValue<T>(sourceValue: T | null): PresenceValue<T> {
  const [state, dispatch] = useReducer(presenceReducer<T>, sourceValue, createPresenceState)
  const [reducedMotion, setReducedMotion] = useState(false)

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    return subscribeToReducedMotion(mediaQuery, setReducedMotion)
  }, [])

  useEffect(() => {
    dispatch({ reducedMotion, type: 'source-changed', value: sourceValue })
  }, [reducedMotion, sourceValue])

  useEffect(() => {
    if (reducedMotion && state.phase === 'exiting') {
      dispatch({ generation: state.generation, type: 'exit-completed' })
    }
  }, [reducedMotion, state.generation, state.phase])

  const completeExit = useCallback((): void => {
    if (state.phase === 'exiting') {
      dispatch({ generation: state.generation, type: 'exit-completed' })
    }
  }, [state.generation, state.phase])

  return { ...state, completeExit }
}
