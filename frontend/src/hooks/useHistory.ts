import { useState } from 'react'

import { apiGet } from '../api/client'
import type { HistoryItem } from '../types'
import { getApiUrl, getIsoTime } from '../utils/mainPage'

type ShowAlert = (text: string, title?: string) => void

type HistoryState = {
  readonly histEnd: string
  readonly histStart: string
  readonly historyDetailIndex: number | null
  readonly historyItems: HistoryItem[]
  readonly historyLoading: boolean
  readonly historyOpen: boolean
  readonly fetchHistory: (manual: boolean, silent: boolean, showAlert: ShowAlert) => Promise<void>
  readonly openHistory: (showAlert: ShowAlert) => Promise<void>
  readonly resetHistory: () => void
  readonly setHistEnd: (value: string) => void
  readonly setHistStart: (value: string) => void
  readonly setHistoryDetailIndex: (index: number | null) => void
  readonly setHistoryOpen: (open: boolean) => void
}

export function useHistory(accountId: string, currentSubId: string): HistoryState {
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([])
  const [historyDetailIndex, setHistoryDetailIndex] = useState<number | null>(null)
  const [histStart, setHistStart] = useState('')
  const [histEnd, setHistEnd] = useState('')
  const [historyCache, setHistoryCache] = useState<Record<string, HistoryItem[]>>({})

  const fetchHistory = async (manual: boolean, silent: boolean, showAlert: ShowAlert): Promise<void> => {
    if (!currentSubId) return
    const now = new Date()
    const start = histStart || new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0]
    const end = histEnd || new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0]
    const startStr = getIsoTime(new Date(start))
    const endStr = getIsoTime(new Date(end), true)
    const cacheKey = `${currentSubId}_${startStr}_${endStr}`
    if (!manual && historyCache[cacheKey]) {
      setHistoryItems(historyCache[cacheKey])
      return
    }
    if (!silent) setHistoryLoading(true)
    try {
      const url = getApiUrl(`/api/history?subscriptionId=${currentSubId}&startDate=${startStr}&endDate=${endStr}&_t=${Date.now()}`, accountId)
      const data = await apiGet<{ status?: string; data?: HistoryItem[]; message?: string }>(url)
      if (data.status === 'success') {
        const next = data.data || []
        setHistoryItems(next)
        setHistoryCache((previous) => ({ ...previous, [cacheKey]: next }))
      } else if (!silent) {
        showAlert(data.message || '查询失败')
      }
    } catch {
      if (!silent) showAlert('网络错误')
    } finally {
      if (!silent) setHistoryLoading(false)
    }
  }

  const openHistory = async (showAlert: ShowAlert): Promise<void> => {
    const now = new Date()
    if (!histStart || !histEnd) {
      setHistStart(new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0])
      setHistEnd(new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0])
    }
    setHistoryOpen(true)
    if (historyItems.length === 0) await fetchHistory(true, false, showAlert)
  }

  const resetHistory = (): void => {
    setHistoryItems([])
    setHistoryDetailIndex(null)
  }

  return {
    fetchHistory,
    histEnd,
    histStart,
    historyDetailIndex,
    historyItems,
    historyLoading,
    historyOpen,
    openHistory,
    resetHistory,
    setHistEnd,
    setHistStart,
    setHistoryDetailIndex,
    setHistoryOpen,
  }
}
