import { useEffect, useMemo, useState } from 'react'

import { apiGet } from '../api/client'
import type { CmnCheckResponse } from '../types'
import { parseCmnPattern } from '../utils/cmnPattern'
import { getApiUrl } from '../utils/mainPage'

type ShowAlert = (text: string, title?: string) => void
type OpenPurchase = (title: string, price: number, source: 'cmn') => void

export const CMN_REFRESH_COOLDOWN_SECONDS = 3

export function useCmn(accountId: string, currentSubId: string) {
  const [cmnLoading, setCmnLoading] = useState(false)
  const [cmnError, setCmnError] = useState('')
  const [cmnData, setCmnData] = useState<CmnCheckResponse['data'] | null>(null)
  const [cmnNumbers, setCmnNumbers] = useState<string[]>([])
  const [cmnNumbersLoading, setCmnNumbersLoading] = useState(false)
  const [selectedNumber, setSelectedNumber] = useState<string | null>(null)
  const [cmnCanRefresh, setCmnCanRefresh] = useState(true)
  const [cmnCooldown, setCmnCooldown] = useState(0)
  const [cmnPattern, setCmnPattern] = useState('')
  const parsedCmnPattern = useMemo(() => parseCmnPattern(cmnPattern), [cmnPattern])

  useEffect(() => {
    if (cmnCooldown <= 0) return
    const timer = window.setInterval(() => {
      setCmnCooldown((previous) => {
        const next = previous - 1
        if (next <= 0) {
          setCmnCanRefresh(true)
          window.clearInterval(timer)
          return 0
        }
        return next
      })
    }, 1000)
    return () => window.clearInterval(timer)
  }, [cmnCooldown])

  const checkCmnEligibility = async (): Promise<void> => {
    if (!currentSubId) return
    setCmnLoading(true)
    setCmnError('')
    try {
      const url = getApiUrl(`/api/cmn/check?subscriptionId=${currentSubId}`, accountId)
      const data = await apiGet<CmnCheckResponse>(url)
      if (data.status === 'success' && data.data) {
        setCmnData(data.data)
      } else {
        setCmnData(null)
        setCmnError(data.message || '无法使用换号服务')
      }
    } catch {
      setCmnData(null)
      setCmnError('网络错误')
    } finally {
      setCmnLoading(false)
    }
  }

  const refreshCmnNumbers = async (showAlert: ShowAlert): Promise<void> => {
    if (!cmnCanRefresh || !currentSubId) return
    setCmnCanRefresh(false)
    setCmnNumbersLoading(true)
    setCmnNumbers([])
    try {
      const url = getApiUrl(`/api/cmn/numbers?subscriptionId=${currentSubId}`, accountId)
      const data = await apiGet<{ status?: string; numbers?: string[]; message?: string }>(url)
      if (data.status === 'success') {
        setSelectedNumber(null)
        setCmnNumbers(data.numbers || [])
        setCmnCooldown(CMN_REFRESH_COOLDOWN_SECONDS)
      } else {
        setCmnCanRefresh(true)
        showAlert(data.message || '获取号码失败')
      }
    } catch {
      setCmnCanRefresh(true)
      showAlert('请求失败')
    } finally {
      setCmnNumbersLoading(false)
    }
  }

  const submitChangeNumber = (showAlert: ShowAlert, openPurchase: OpenPurchase): void => {
    if (!selectedNumber) {
      showAlert('请先选择号码', '提示')
      return
    }
    if (!cmnData) return
    openPurchase(`更换号码: ${selectedNumber}`, cmnData.price, 'cmn')
  }

  return { checkCmnEligibility, cmnCanRefresh, cmnCooldown, cmnData, cmnError, cmnLoading, cmnNumbers, cmnNumbersLoading, cmnPattern, parsedCmnPattern, refreshCmnNumbers, selectedNumber, setCmnPattern, setSelectedNumber, submitChangeNumber }
}
