import { useEffect, useLayoutEffect, useRef } from 'react'

import type { CmnAutoRefreshState, CmnNumbersMode } from '@/hooks/useCmn'
import { UiIcon } from './UiIcon'
import { WaitingState, type WaitingPhase } from './WaitingState'

const LONG_PRESS_MS = 550

export type CmnRefreshButtonState =
  | { readonly kind: 'running'; readonly attempt: number; readonly phase: WaitingPhase }
  | { readonly kind: 'loading' }
  | { readonly kind: 'cooldown'; readonly seconds: number }
  | { readonly kind: 'idle' }

type CmnRefreshButtonStateInput = {
  readonly autoRefresh: CmnAutoRefreshState
  readonly canRefresh: boolean
  readonly cooldown: number
  readonly numbersLoading: boolean
}

// eslint-disable-next-line react-refresh/only-export-components
export function resolveCmnRefreshButtonState({
  autoRefresh,
  canRefresh,
  cooldown,
  numbersLoading,
}: CmnRefreshButtonStateInput): CmnRefreshButtonState {
  if (autoRefresh.kind === 'running') return { kind: 'running', attempt: autoRefresh.attempt, phase: autoRefresh.phase }
  if (numbersLoading) return { kind: 'loading' }
  if (!canRefresh && cooldown > 0) return { kind: 'cooldown', seconds: cooldown }
  return { kind: 'idle' }
}

type CmnRefreshButtonProps = CmnRefreshButtonStateInput & {
  readonly mode: CmnNumbersMode
  readonly onAutoRefreshCancel: () => void
  readonly onAutoRefreshStart: () => void
  readonly onRefresh: () => void
  readonly pattern: string
  readonly validPattern: boolean
  readonly visible: boolean
}

function renderCopy(state: CmnRefreshButtonState, mode: CmnNumbersMode, timerId: string | undefined): JSX.Element {
  switch (state.kind) {
    case 'running':
      return (
        <span className="cmn-auto-refresh-copy">
          <span>自动查找 {state.attempt}/20</span>
          <span>点击取消</span>
        </span>
      )
    case 'loading':
      return <span>{mode === 'initial' ? '正在获取号码…' : '正在换一批…'}</span>
    case 'cooldown':
      return (
        <span>
          换一批（
          <span className="cmn-refresh-countdown" id={timerId}>
            {state.seconds}s
          </span>
          ）
        </span>
      )
    case 'idle':
      return <span>{mode === 'initial' ? '获取一组新号码' : '换一批'}</span>
    default:
      return state satisfies never
  }
}

export function CmnRefreshButton({
  autoRefresh,
  canRefresh,
  cooldown,
  mode,
  numbersLoading,
  onAutoRefreshCancel,
  onAutoRefreshStart,
  onRefresh,
  pattern,
  validPattern,
  visible,
}: CmnRefreshButtonProps): JSX.Element {
  const longPressTimerRef = useRef<number | null>(null)
  const suppressClickFallbackRef = useRef<number | null>(null)
  const armedPointerRef = useRef<number | null>(null)
  const suppressClickRef = useRef(false)
  const state = resolveCmnRefreshButtonState({ autoRefresh, canRefresh, cooldown, numbersLoading })
  const running = state.kind === 'running'
  const gestureEnabled = mode === 'subsequent'
  const gestureEligibilityRef = useRef({ canRefresh, onAutoRefreshStart, pattern, running, validPattern, visible })

  const clearLongPress = (): void => {
    if (longPressTimerRef.current !== null) window.clearTimeout(longPressTimerRef.current)
    longPressTimerRef.current = null
    armedPointerRef.current = null
  }

  const clearClickSuppression = (): void => {
    if (suppressClickFallbackRef.current !== null) window.clearTimeout(suppressClickFallbackRef.current)
    suppressClickFallbackRef.current = null
    suppressClickRef.current = false
  }

  useEffect(
    () => () => {
      clearLongPress()
      clearClickSuppression()
    },
    [],
  )

  useLayoutEffect(() => {
    gestureEligibilityRef.current = { canRefresh, onAutoRefreshStart, pattern, running, validPattern, visible }
    clearLongPress()
  }, [canRefresh, onAutoRefreshStart, pattern, running, validPattern, visible])

  const handlePointerDown = (event: React.PointerEvent<HTMLButtonElement>): void => {
    clearClickSuppression()
    if (!gestureEnabled || event.button !== 0 || !event.isPrimary || running || !validPattern || !canRefresh) return
    armedPointerRef.current = event.pointerId
    const pointerId = event.pointerId
    const armedEligibility = gestureEligibilityRef.current
    event.currentTarget.setPointerCapture?.(event.pointerId)
    longPressTimerRef.current = window.setTimeout(() => {
      longPressTimerRef.current = null
      const current = gestureEligibilityRef.current
      if (
        armedPointerRef.current !== pointerId ||
        !current.canRefresh ||
        current.running ||
        !current.validPattern ||
        !current.visible ||
        current.pattern !== armedEligibility.pattern ||
        current.onAutoRefreshStart !== armedEligibility.onAutoRefreshStart
      )
        return
      suppressClickRef.current = true
      current.onAutoRefreshStart()
    }, LONG_PRESS_MS)
  }

  const handlePointerEnd = (event: React.PointerEvent<HTMLButtonElement>): void => {
    const pointerWasArmed = armedPointerRef.current === event.pointerId
    if (!pointerWasArmed && !suppressClickRef.current) return
    if (pointerWasArmed) clearLongPress()
    if (event.currentTarget.hasPointerCapture?.(event.pointerId))
      event.currentTarget.releasePointerCapture?.(event.pointerId)
    if (suppressClickRef.current) {
      suppressClickFallbackRef.current = window.setTimeout(clearClickSuppression, 0)
    }
  }

  const handleRefreshClick = (): void => {
    if (suppressClickRef.current) {
      clearClickSuppression()
      return
    }
    if (running) {
      onAutoRefreshCancel()
      return
    }
    onRefresh()
  }

  const handleContextMenu = (event: React.MouseEvent<HTMLButtonElement>): void => {
    if (armedPointerRef.current !== null) event.preventDefault()
  }

  const busy = state.kind === 'running' || state.kind === 'loading'
  const disabled = state.kind === 'loading' || state.kind === 'cooldown' || (state.kind === 'idle' && !canRefresh)
  const className = [
    'refresh-btn',
    mode === 'subsequent' ? 'cmn-auto-refresh-button' : '',
    state.kind === 'running' ? 'is-running' : '',
    state.kind === 'loading' ? 'is-loading' : '',
  ]
    .filter(Boolean)
    .join(' ')
  const describedBy =
    mode === 'subsequent'
      ? [validPattern ? 'cmn-auto-refresh-hint' : '', 'cmn-auto-refresh-status'].filter(Boolean).join(' ')
      : undefined

  const waitingPhase: WaitingPhase | null =
    state.kind === 'running'
      ? state.phase
      : state.kind === 'loading'
        ? 'requesting'
        : state.kind === 'cooldown'
          ? 'cooldown'
          : null
  const timerId = mode === 'subsequent' ? 'refresh-timer' : undefined

  return (
    <button
      type="button"
      className={className}
      id={mode === 'initial' ? 'initLoadBtn' : 'refreshNumBtn'}
      disabled={disabled}
      aria-busy={busy || undefined}
      aria-describedby={describedBy}
      onClick={handleRefreshClick}
      onContextMenu={handleContextMenu}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerEnd}
      onPointerCancel={handlePointerEnd}
      onLostPointerCapture={handlePointerEnd}
    >
      {waitingPhase === null ? (
        <>
          <UiIcon className="refresh-btn-icon" name={mode === 'initial' ? 'search' : 'refresh'} />
          {renderCopy(state, mode, timerId)}
        </>
      ) : (
        <WaitingState iconClassName="refresh-btn-icon" phase={waitingPhase}>
          {renderCopy(state, mode, timerId)}
        </WaitingState>
      )}
    </button>
  )
}
