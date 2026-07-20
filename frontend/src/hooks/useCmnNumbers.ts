import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react'

import { apiFetch } from '@/api/client'
import { toUserFacingApiError } from '@/utils'
import type { CmnRefreshOutcome } from '@/utils/cmnAutoRefresh'

type ShowAlert = (text: string, title?: string) => void
type RefreshMode = 'manual' | 'auto'

type CmnLifecycle = {
  readonly mountedRef: MutableRefObject<boolean>
  readonly scopeGenerationRef: MutableRefObject<number>
}

type CmnNumbersOptions = {
  readonly accountId: string
  readonly currentSubId: string
  readonly lifecycle: CmnLifecycle
}

export const CMN_REFRESH_COOLDOWN_SECONDS = 3

export type CmnNumbersMode = 'initial' | 'subsequent'

export function useCmnNumbers({ accountId, currentSubId, lifecycle }: CmnNumbersOptions) {
  const { mountedRef, scopeGenerationRef } = lifecycle
  const [cmnNumbers, setCmnNumbers] = useState<string[]>([])
  const [cmnNumbersLoading, setCmnNumbersLoading] = useState(false)
  const [cmnNumbersMode, setCmnNumbersMode] = useState<CmnNumbersMode>('initial')
  const [selectedNumber, setSelectedNumber] = useState<string | null>(null)
  const [cmnCanRefresh, setCmnCanRefresh] = useState(true)
  const [cmnCooldown, setCmnCooldown] = useState(0)
  const requestIdRef = useRef(0)
  const inFlightRef = useRef(false)
  const canRefreshAtRef = useRef(0)
  const refreshAbortRef = useRef<AbortController | null>(null)

  useEffect(() => () => refreshAbortRef.current?.abort(), [])

  useEffect(() => {
    inFlightRef.current = false
    canRefreshAtRef.current = 0
    setCmnCanRefresh(true)
    setCmnCooldown(0)
    setCmnNumbersLoading(false)
    setCmnNumbers([])
    setCmnNumbersMode('initial')
    setSelectedNumber(null)
  }, [accountId, currentSubId])

  useEffect(() => {
    if (cmnCooldown <= 0) return
    const timer = window.setInterval(() => {
      const remaining = Math.max(0, Math.ceil((canRefreshAtRef.current - Date.now()) / 1000))
      setCmnCooldown(remaining)
      if (remaining === 0) {
        setCmnCanRefresh(true)
        window.clearInterval(timer)
      }
    }, 250)
    return () => window.clearInterval(timer)
  }, [cmnCooldown])

  const requestCmnNumbers = useCallback(
    async (showAlert: ShowAlert, mode: RefreshMode, signal?: AbortSignal): Promise<CmnRefreshOutcome> => {
      if (!currentSubId || inFlightRef.current || Date.now() < canRefreshAtRef.current) return { kind: 'unavailable' }

      const controller = signal ? null : new AbortController()
      const requestSignal = signal ?? controller?.signal
      if (!requestSignal) return { kind: 'unavailable' }
      refreshAbortRef.current = controller
      inFlightRef.current = true
      const requestId = requestIdRef.current + 1
      requestIdRef.current = requestId
      const scope = scopeGenerationRef.current
      const isCurrent = (): boolean =>
        mountedRef.current &&
        !requestSignal.aborted &&
        requestId === requestIdRef.current &&
        scope === scopeGenerationRef.current

      setCmnCanRefresh(false)
      setCmnNumbersLoading(true)
      if (mode === 'manual') setCmnNumbers([])

      try {
        const formData = new FormData()
        formData.append('subscriptionId', currentSubId)
        if (accountId) formData.append('account_id', accountId)
        const response = await apiFetch('/api/cmn/numbers', {
          method: 'POST',
          body: formData,
          signal: requestSignal,
        })
        if (!response.ok) {
          const bodyText = await response.text()
          let message = '获取号码失败'
          const parsedMessage = (() => {
            try {
              const parsed = JSON.parse(bodyText) as { message?: string }
              return parsed.message
            } catch {
              return undefined
            }
          })()
          if (parsedMessage) message = parsedMessage
          if (!isCurrent()) return { kind: 'unavailable' }
          setCmnCanRefresh(true)
          if (mode === 'manual') showAlert(message)
          return { kind: 'error' }
        }
        const data = (await response.json()) as {
          status?: string
          numbers?: string[]
          message?: string
        }
        if (!isCurrent()) return { kind: 'unavailable' }
        if (data.status !== 'success') {
          setCmnCanRefresh(true)
          if (mode === 'manual') showAlert(data.message || '获取号码失败')
          return { kind: 'error' }
        }

        const numbers = data.numbers || []
        setSelectedNumber(null)
        setCmnNumbers(numbers)
        setCmnNumbersMode('subsequent')
        canRefreshAtRef.current = Date.now() + CMN_REFRESH_COOLDOWN_SECONDS * 1000
        setCmnCooldown(CMN_REFRESH_COOLDOWN_SECONDS)
        return { kind: 'success', numbers }
      } catch (error: unknown) {
        if (requestSignal.aborted) return { kind: 'unavailable' }
        if (isCurrent()) {
          setCmnCanRefresh(true)
          if (mode === 'manual') showAlert(toUserFacingApiError(error, '请求失败'))
          return { kind: 'error' }
        }
        return { kind: 'unavailable' }
      } finally {
        if (requestId === requestIdRef.current) {
          inFlightRef.current = false
          refreshAbortRef.current = null
          if (isCurrent()) setCmnNumbersLoading(false)
        }
      }
    },
    [accountId, currentSubId, mountedRef, scopeGenerationRef],
  )

  const refreshCmnNumbers = useCallback(
    async (showAlert: ShowAlert): Promise<CmnRefreshOutcome> => requestCmnNumbers(showAlert, 'manual'),
    [requestCmnNumbers],
  )

  const canStartAutoRefresh = useCallback(
    (): boolean => Boolean(currentSubId) && !inFlightRef.current && Date.now() >= canRefreshAtRef.current,
    [currentSubId],
  )

  const releaseAutoRequestAfterCancel = useCallback((): void => {
    requestIdRef.current += 1
    inFlightRef.current = false
    if (Date.now() >= canRefreshAtRef.current) {
      canRefreshAtRef.current = 0
      setCmnCanRefresh(true)
      setCmnCooldown(0)
    }
    if (mountedRef.current) setCmnNumbersLoading(false)
  }, [mountedRef])

  return {
    canStartAutoRefresh,
    cmnCanRefresh,
    cmnCooldown,
    cmnNumbers,
    cmnNumbersLoading,
    cmnNumbersMode,
    refreshCmnNumbers,
    releaseAutoRequestAfterCancel,
    requestCmnNumbers,
    selectedNumber,
    setSelectedNumber,
  }
}
