import { useEffect, useRef } from 'react'

import { useCmnAutoRefresh } from './useCmnAutoRefresh'
import { useCmnEligibility } from './useCmnEligibility'
import { useCmnNumbers } from './useCmnNumbers'

export type { CmnAutoRefreshState } from './useCmnAutoRefresh'
export { CMN_REFRESH_COOLDOWN_SECONDS } from './useCmnNumbers'
export type { CmnNumbersMode } from './useCmnNumbers'

type ShowAlert = (text: string, title?: string) => void
type OpenPurchase = (title: string, price: number, source: 'cmn') => void

export function useCmn(accountId: string, currentSubId: string, visible: boolean) {
  const mountedRef = useRef(true)
  const scopeGenerationRef = useRef(0)
  const lifecycle = { mountedRef, scopeGenerationRef }

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      scopeGenerationRef.current += 1
    }
  }, [])

  useEffect(() => {
    scopeGenerationRef.current += 1
  }, [accountId, currentSubId])

  const numbers = useCmnNumbers({ accountId, currentSubId, lifecycle })
  const autoRefresh = useCmnAutoRefresh({
    accountId,
    currentSubId,
    lifecycle,
    numbers,
    visible,
  })
  const eligibility = useCmnEligibility({
    accountId,
    cancelCmnAutoRefresh: autoRefresh.cancelCmnAutoRefresh,
    currentSubId,
    lifecycle,
  })

  const submitChangeNumber = (showAlert: ShowAlert, openPurchase: OpenPurchase): void => {
    if (!numbers.selectedNumber) {
      showAlert('请先选择号码', '提示')
      return
    }
    if (!eligibility.cmnData) return
    openPurchase(`更换号码: ${numbers.selectedNumber}`, eligibility.cmnData.price, 'cmn')
  }

  return {
    cancelCmnAutoRefresh: autoRefresh.cancelCmnAutoRefresh,
    changeCmnPattern: autoRefresh.changeCmnPattern,
    checkCmnEligibility: eligibility.checkCmnEligibility,
    cmnAutoRefresh: autoRefresh.cmnAutoRefresh,
    cmnCanRefresh: numbers.cmnCanRefresh,
    cmnCooldown: numbers.cmnCooldown,
    cmnData: eligibility.cmnData,
    cmnError: eligibility.cmnError,
    cmnLoading: eligibility.cmnLoading,
    cmnNumbers: numbers.cmnNumbers,
    cmnNumbersLoading: numbers.cmnNumbersLoading,
    cmnNumbersMode: numbers.cmnNumbersMode,
    cmnPattern: autoRefresh.cmnPattern,
    parsedCmnPattern: autoRefresh.parsedCmnPattern,
    refreshCmnNumbers: numbers.refreshCmnNumbers,
    selectedNumber: numbers.selectedNumber,
    setSelectedNumber: numbers.setSelectedNumber,
    startCmnAutoRefresh: autoRefresh.startCmnAutoRefresh,
    submitChangeNumber,
  }
}
