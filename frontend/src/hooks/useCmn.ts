import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { apiGet } from '@/api/client'
import type { CmnCheckResponse } from '@/types'
import { toUserFacingApiError } from '@/utils'
import {
  CMN_AUTO_REFRESH_MAX_ATTEMPTS,
  type CmnAutoRefreshResult,
  type CmnRefreshOutcome,
  runCmnAutoRefresh,
} from '@/utils/cmnAutoRefresh'
import { parseCmnPattern } from '@/utils/cmnPattern'
import { getApiUrl } from '@/utils/mainPage'

type ShowAlert = (text: string, title?: string) => void
type OpenPurchase = (title: string, price: number, source: 'cmn') => void
type RefreshMode = 'manual' | 'auto'

export type CmnAutoRefreshState =
  | { readonly kind: 'idle'; readonly message: string }
  | { readonly kind: 'running'; readonly attempt: number; readonly message: string }

export const CMN_REFRESH_COOLDOWN_SECONDS = 3

function resultMessage(result: CmnAutoRefreshResult): string {
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

export function useCmn(accountId: string, currentSubId: string, visible: boolean) {
  const [cmnLoading, setCmnLoading] = useState(false)
  const [cmnError, setCmnError] = useState('')
  const [cmnData, setCmnData] = useState<CmnCheckResponse['data'] | null>(null)
  const [cmnNumbers, setCmnNumbers] = useState<string[]>([])
  const [cmnNumbersLoading, setCmnNumbersLoading] = useState(false)
  const [selectedNumber, setSelectedNumber] = useState<string | null>(null)
  const [cmnCanRefresh, setCmnCanRefresh] = useState(true)
  const [cmnCooldown, setCmnCooldown] = useState(0)
  const [cmnPattern, setCmnPattern] = useState('')
  const [cmnAutoRefresh, setCmnAutoRefresh] = useState<CmnAutoRefreshState>({ kind: 'idle', message: '' })
  const parsedCmnPattern = useMemo(() => parseCmnPattern(cmnPattern), [cmnPattern])

  const mountedRef = useRef(true)
  const scopeGenerationRef = useRef(0)
  const requestIdRef = useRef(0)
  const autoRunIdRef = useRef(0)
  const inFlightRef = useRef(false)
  const canRefreshAtRef = useRef(0)
  const refreshAbortRef = useRef<AbortController | null>(null)
  const eligibilityAbortRef = useRef<AbortController | null>(null)
  const autoAbortRef = useRef<AbortController | null>(null)

  const cancelAutoRefresh = useCallback((announce = true): void => {
    autoRunIdRef.current += 1
    const controller = autoAbortRef.current
    controller?.abort()
    autoAbortRef.current = null
    if (controller) {
      requestIdRef.current += 1
      inFlightRef.current = false
      if (Date.now() >= canRefreshAtRef.current) {
        canRefreshAtRef.current = 0
        setCmnCanRefresh(true)
        setCmnCooldown(0)
      }
    }
    if (mountedRef.current) {
      if (controller) setCmnNumbersLoading(false)
      setCmnAutoRefresh({ kind: 'idle', message: announce ? '已取消自动查找' : '' })
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      scopeGenerationRef.current += 1
      eligibilityAbortRef.current?.abort()
      refreshAbortRef.current?.abort()
      cancelAutoRefresh(false)
    }
  }, [cancelAutoRefresh])

  useEffect(() => {
    scopeGenerationRef.current += 1
    eligibilityAbortRef.current?.abort()
    cancelAutoRefresh(false)
    inFlightRef.current = false
    canRefreshAtRef.current = 0
    setCmnCanRefresh(true)
    setCmnCooldown(0)
    setCmnLoading(false)
    setCmnNumbersLoading(false)
    setCmnData(null)
    setCmnError('')
    setCmnNumbers([])
    setSelectedNumber(null)
  }, [accountId, cancelAutoRefresh, currentSubId])

  useEffect(() => {
    if (!visible) cancelAutoRefresh(false)
  }, [cancelAutoRefresh, visible])

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

  const checkCmnEligibility = useCallback(async (): Promise<void> => {
    if (!currentSubId) return
    eligibilityAbortRef.current?.abort()
    const controller = new AbortController()
    eligibilityAbortRef.current = controller
    const scope = scopeGenerationRef.current
    setCmnLoading(true)
    setCmnError('')
    try {
      const url = getApiUrl(`/api/cmn/check?subscriptionId=${currentSubId}`, accountId)
      const data = await apiGet<CmnCheckResponse>(url, { signal: controller.signal })
      if (!mountedRef.current || controller.signal.aborted || scope !== scopeGenerationRef.current) return
      if (data.status === 'success' && data.data) {
        setCmnData(data.data)
      } else {
        setCmnData(null)
        setCmnError(data.message || '无法使用换号服务')
        cancelAutoRefresh(false)
      }
    } catch (error: unknown) {
      if (controller.signal.aborted) return
      if (mountedRef.current && scope === scopeGenerationRef.current) {
        setCmnData(null)
        setCmnError(toUserFacingApiError(error, '网络错误'))
        cancelAutoRefresh(false)
      }
    } finally {
      if (mountedRef.current && !controller.signal.aborted && scope === scopeGenerationRef.current) setCmnLoading(false)
    }
  }, [accountId, cancelAutoRefresh, currentSubId])

  const requestCmnNumbers = useCallback(async (showAlert: ShowAlert, mode: RefreshMode, signal?: AbortSignal): Promise<CmnRefreshOutcome> => {
    if (!currentSubId || inFlightRef.current || Date.now() < canRefreshAtRef.current) return { kind: 'unavailable' }

    const controller = signal ? null : new AbortController()
    const requestSignal = signal ?? controller?.signal
    if (!requestSignal) return { kind: 'unavailable' }
    refreshAbortRef.current = controller
    inFlightRef.current = true
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    const scope = scopeGenerationRef.current
    const isCurrent = (): boolean => mountedRef.current && !requestSignal.aborted && requestId === requestIdRef.current && scope === scopeGenerationRef.current

    setCmnCanRefresh(false)
    setCmnNumbersLoading(true)
    if (mode === 'manual') setCmnNumbers([])

    try {
      const url = getApiUrl(`/api/cmn/numbers?subscriptionId=${currentSubId}`, accountId)
      const data = await apiGet<{ status?: string; numbers?: string[]; message?: string }>(url, { signal: requestSignal })
      if (!isCurrent()) return { kind: 'unavailable' }
      if (data.status !== 'success') {
        setCmnCanRefresh(true)
        if (mode === 'manual') showAlert(data.message || '获取号码失败')
        return { kind: 'error' }
      }

      const numbers = data.numbers || []
      setSelectedNumber(null)
      setCmnNumbers(numbers)
      canRefreshAtRef.current = Date.now() + (CMN_REFRESH_COOLDOWN_SECONDS * 1000)
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
  }, [accountId, currentSubId])

  const refreshCmnNumbers = useCallback(async (showAlert: ShowAlert): Promise<CmnRefreshOutcome> => requestCmnNumbers(showAlert, 'manual'), [requestCmnNumbers])

  const startCmnAutoRefresh = useCallback((showAlert: ShowAlert): void => {
    if (cmnAutoRefresh.kind === 'running' || parsedCmnPattern.kind === 'empty' || parsedCmnPattern.kind === 'invalid') return
    if (inFlightRef.current || Date.now() < canRefreshAtRef.current || !currentSubId) return

    const controller = new AbortController()
    const runId = autoRunIdRef.current + 1
    const scope = scopeGenerationRef.current
    autoRunIdRef.current = runId
    autoAbortRef.current = controller
    setCmnAutoRefresh({ kind: 'running', attempt: 0, message: '自动查找已开始' })

    void runCmnAutoRefresh({
      pattern: cmnPattern,
      signal: controller.signal,
      request: (signal) => requestCmnNumbers(showAlert, 'auto', signal),
      onAttemptStart: (attempt) => {
        if (mountedRef.current && runId === autoRunIdRef.current && scope === scopeGenerationRef.current) {
          setCmnAutoRefresh({ kind: 'running', attempt, message: `正在自动查找第 ${attempt} 批号码` })
        }
      },
    }).then((result) => {
      if (!mountedRef.current || runId !== autoRunIdRef.current || scope !== scopeGenerationRef.current) return
      autoAbortRef.current = null
      setCmnAutoRefresh({ kind: 'idle', message: resultMessage(result) })
    })
  }, [cmnAutoRefresh.kind, cmnPattern, currentSubId, parsedCmnPattern.kind, requestCmnNumbers])

  const changeCmnPattern = useCallback((pattern: string): void => {
    cancelAutoRefresh(false)
    setCmnPattern(pattern)
  }, [cancelAutoRefresh])

  const submitChangeNumber = (showAlert: ShowAlert, openPurchase: OpenPurchase): void => {
    if (!selectedNumber) {
      showAlert('请先选择号码', '提示')
      return
    }
    if (!cmnData) return
    openPurchase(`更换号码: ${selectedNumber}`, cmnData.price, 'cmn')
  }

  return { cancelCmnAutoRefresh: cancelAutoRefresh, changeCmnPattern, checkCmnEligibility, cmnAutoRefresh, cmnCanRefresh, cmnCooldown, cmnData, cmnError, cmnLoading, cmnNumbers, cmnNumbersLoading, cmnPattern, parsedCmnPattern, refreshCmnNumbers, selectedNumber, setSelectedNumber, startCmnAutoRefresh, submitChangeNumber }
}
