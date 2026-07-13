import { useEffect, useRef, type Dispatch, type SetStateAction } from 'react'

import { apiGet } from '@/api/client'
import type { Category, Plan } from '@/types'
import { getApiUrl } from '@/utils/mainPage'
import { sortPlansByPrice } from '@/utils/profileBootstrap'

type ShowAlert = (text: string, title?: string) => void

type SubscriptionBootstrapScope = {
  readonly accountId: string
  readonly category: Category
  readonly currentSubId: string
  readonly noNumberMode: boolean
  readonly setBalance: Dispatch<SetStateAction<string>>
  readonly setPlans: Dispatch<SetStateAction<Plan[]>>
  readonly setPlansLoading: Dispatch<SetStateAction<boolean>>
}

type SubscriptionBootstrapActions = {
  readonly checkCmnEligibility: () => Promise<void>
  readonly fetchHistory: (manual: boolean, silent: boolean, showAlert: ShowAlert) => Promise<void>
  readonly fetchInbox: (force: boolean, showAlert: ShowAlert) => Promise<void>
  readonly resetCart: () => void
  readonly resetHistory: () => void
  readonly showAlert: ShowAlert
}

export function useSubscriptionBootstrap(
  scope: SubscriptionBootstrapScope,
  actions: SubscriptionBootstrapActions,
): void {
  const { accountId, category, currentSubId, noNumberMode, setBalance, setPlans, setPlansLoading } = scope
  const actionsRef = useRef(actions)

  useEffect(() => {
    actionsRef.current = actions
  }, [actions])

  useEffect(() => {
    if (!currentSubId && !noNumberMode) return
    let cancelled = false

    const fetchBalance = async (): Promise<void> => {
      if (noNumberMode) {
        setBalance('0.0')
        return
      }
      try {
        const url = getApiUrl(`/api/balance?subscriptionId=${currentSubId}&_t=${Date.now()}`, accountId)
        const data = await apiGet<{ status?: string; balance?: string | number }>(url)
        if (!cancelled) setBalance(data.status === 'success' ? String(data.balance ?? '0.0') : '0.0')
      } catch {
        if (!cancelled) setBalance('0.0')
      }
    }

    const fetchPlans = async (): Promise<void> => {
      setPlansLoading(true)
      try {
        const subParam = noNumberMode ? 'none' : currentSubId
        const url = getApiUrl(`/api/plans?subscriptionId=${subParam}`, accountId)
        const data = await apiGet<{ status?: string; plans?: Plan[] }>(url)
        if (!cancelled) setPlans(data.status === 'success' ? sortPlansByPrice(data.plans || []) : [])
      } catch {
        if (!cancelled) setPlans([])
      } finally {
        if (!cancelled) setPlansLoading(false)
      }
    }

    const currentActions = actionsRef.current
    void fetchBalance()
    void fetchPlans()
    if (!noNumberMode) {
      void currentActions.fetchInbox(false, currentActions.showAlert)
      void currentActions.fetchHistory(false, true, currentActions.showAlert)
    }
    currentActions.resetCart()
    currentActions.resetHistory()
    if (category === 'CMN' && !noNumberMode) void currentActions.checkCmnEligibility()

    return () => {
      cancelled = true
    }
  }, [accountId, category, currentSubId, noNumberMode, setBalance, setPlans, setPlansLoading])
}
