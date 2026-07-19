import { useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'

import {
  CMN_AUTO_REFRESH_MAX_ATTEMPTS,
  type CmnAutoRefreshPhase,
  type CmnAutoRefreshResult,
  type CmnRefreshOutcome,
  runCmnAutoRefresh,
} from '@/utils/cmnAutoRefresh'
import { parseCmnPattern } from '@/utils/cmnPattern'

type ShowAlert = (text: string, title?: string) => void

type CmnLifecycle = {
  readonly mountedRef: MutableRefObject<boolean>
  readonly scopeGenerationRef: MutableRefObject<number>
}

type CmnAutoRefreshNumbers = {
  readonly canStartAutoRefresh: () => boolean
  readonly releaseAutoRequestAfterCancel: () => void
  readonly requestCmnNumbers: (
    showAlert: ShowAlert,
    mode: 'manual' | 'auto',
    signal?: AbortSignal,
  ) => Promise<CmnRefreshOutcome>
}

type CmnAutoRefreshOptions = {
  readonly accountId: string
  readonly currentSubId: string
  readonly lifecycle: CmnLifecycle
  readonly numbers: CmnAutoRefreshNumbers
  readonly visible: boolean
}

export type CmnAutoRefreshState =
  | { readonly kind: 'idle'; readonly message: string }
  | {
      readonly kind: 'running'
      readonly attempt: number
      readonly phase: CmnAutoRefreshPhase
      readonly message: string
    }

export function cmnAutoRefreshResultMessage(result: CmnAutoRefreshResult): string {
  switch (result.kind) {
    case 'matched':
      return `已在第 ${result.attempts} 次查找中找到匹配号码`
    case 'exhausted':
      return `已完成 ${CMN_AUTO_REFRESH_MAX_ATTEMPTS} 次查找，未找到匹配号码`
    case 'aborted':
      return '已取消自动查找'
    case 'unavailable':
      return '自动查找当前不可用'
    case 'error':
      return '自动查找因请求失败而停止'
    default:
      return result satisfies never
  }
}

export function useCmnAutoRefresh({ accountId, currentSubId, lifecycle, numbers, visible }: CmnAutoRefreshOptions) {
  const { mountedRef, scopeGenerationRef } = lifecycle
  const { canStartAutoRefresh, releaseAutoRequestAfterCancel, requestCmnNumbers } = numbers
  const [cmnPattern, setCmnPattern] = useState('')
  const [cmnAutoRefresh, setCmnAutoRefresh] = useState<CmnAutoRefreshState>({ kind: 'idle', message: '' })
  const parsedCmnPattern = useMemo(() => parseCmnPattern(cmnPattern), [cmnPattern])
  const autoRunIdRef = useRef(0)
  const autoAbortRef = useRef<AbortController | null>(null)

  const cancelCmnAutoRefresh = useCallback(
    (announce = true): void => {
      autoRunIdRef.current += 1
      const controller = autoAbortRef.current
      controller?.abort()
      autoAbortRef.current = null
      if (controller) releaseAutoRequestAfterCancel()
      if (mountedRef.current) setCmnAutoRefresh({ kind: 'idle', message: announce ? '已取消自动查找' : '' })
    },
    [mountedRef, releaseAutoRequestAfterCancel],
  )

  useEffect(() => () => cancelCmnAutoRefresh(false), [cancelCmnAutoRefresh])

  useEffect(() => {
    cancelCmnAutoRefresh(false)
  }, [accountId, cancelCmnAutoRefresh, currentSubId])

  useEffect(() => {
    if (!visible) cancelCmnAutoRefresh(false)
  }, [cancelCmnAutoRefresh, visible])

  const startCmnAutoRefresh = useCallback(
    (showAlert: ShowAlert): void => {
      if (cmnAutoRefresh.kind === 'running' || parsedCmnPattern.kind === 'empty' || parsedCmnPattern.kind === 'invalid')
        return
      if (!canStartAutoRefresh() || !currentSubId) return

      const controller = new AbortController()
      const runId = autoRunIdRef.current + 1
      const scope = scopeGenerationRef.current
      autoRunIdRef.current = runId
      autoAbortRef.current = controller
      setCmnAutoRefresh({ kind: 'running', attempt: 0, phase: 'requesting', message: '自动查找已开始' })

      void runCmnAutoRefresh({
        pattern: cmnPattern,
        signal: controller.signal,
        request: (signal) => requestCmnNumbers(showAlert, 'auto', signal),
        onProgress: ({ attempt, phase }) => {
          if (mountedRef.current && runId === autoRunIdRef.current && scope === scopeGenerationRef.current) {
            setCmnAutoRefresh({ kind: 'running', attempt, phase, message: `正在自动查找第 ${attempt} 批号码` })
          }
        },
      }).then((result) => {
        if (!mountedRef.current || runId !== autoRunIdRef.current || scope !== scopeGenerationRef.current) return
        autoAbortRef.current = null
        setCmnAutoRefresh({ kind: 'idle', message: cmnAutoRefreshResultMessage(result) })
      })
    },
    [
      canStartAutoRefresh,
      cmnAutoRefresh.kind,
      cmnPattern,
      currentSubId,
      mountedRef,
      parsedCmnPattern.kind,
      requestCmnNumbers,
      scopeGenerationRef,
    ],
  )

  const changeCmnPattern = useCallback(
    (pattern: string): void => {
      cancelCmnAutoRefresh(false)
      setCmnPattern(pattern)
    },
    [cancelCmnAutoRefresh],
  )

  return {
    cancelCmnAutoRefresh,
    changeCmnPattern,
    cmnAutoRefresh,
    cmnPattern,
    parsedCmnPattern,
    startCmnAutoRefresh,
  }
}
