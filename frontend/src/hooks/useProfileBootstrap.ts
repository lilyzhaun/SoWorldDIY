import { useEffect, type Dispatch, type SetStateAction } from 'react'

import { apiFetch, apiGet } from '@/api/client'
import type { AvailableAccount, Category, Plan, ProfileResponse, Subscription } from '@/types'
import { getApiUrl } from '@/utils/mainPage'

type ShowAlert = (text: string, title?: string) => void

type ProfileBootstrapDeps = {
  readonly accountId: string
  readonly currentSubId: string
  readonly setCurrentSubId: Dispatch<SetStateAction<string>>
  readonly noNumberMode: boolean
  readonly setNoNumberMode: Dispatch<SetStateAction<boolean>>
  readonly setLoading: Dispatch<SetStateAction<boolean>>
  readonly setSubscriptions: Dispatch<SetStateAction<Subscription[]>>
  readonly setAvailableAccounts: Dispatch<SetStateAction<AvailableAccount[]>>
  readonly setBalance: Dispatch<SetStateAction<string>>
  readonly setPlans: Dispatch<SetStateAction<Plan[]>>
  readonly setPlansLoading: Dispatch<SetStateAction<boolean>>
  readonly category: Category
  readonly fetchInbox: (force: boolean, showAlert: ShowAlert) => Promise<void>
  readonly fetchHistory: (manual: boolean, silent: boolean, showAlert: ShowAlert) => Promise<void>
  readonly resetCart: () => void
  readonly resetHistory: () => void
  readonly checkCmnEligibility: () => Promise<void>
  readonly showAlert: ShowAlert
}

export function useProfileBootstrap(deps: ProfileBootstrapDeps): void {
  const {
    accountId,
    currentSubId,
    setCurrentSubId,
    noNumberMode,
    setNoNumberMode,
    setLoading,
    setSubscriptions,
    setAvailableAccounts,
    setBalance,
    setPlans,
    setPlansLoading,
    category,
    fetchInbox,
    fetchHistory,
    resetCart,
    resetHistory,
    checkCmnEligibility,
    showAlert,
  } = deps

  useEffect(() => {
    let cancelled = false
    const init = async (): Promise<void> => {
      try {
        const apiUrl = getApiUrl(`/api/profile?_t=${Date.now()}`, accountId)
        const response = await apiFetch(apiUrl, { headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' } })
        const contentType = response.headers.get('content-type')
        if (response.redirected || (contentType && !contentType.includes('application/json'))) {
          window.location.href = '/'
          return
        }
        if (!response.ok) throw new Error(`API Error: ${response.status}`)

        const data = (await response.json()) as ProfileResponse
        if (data.status !== 'success') {
          window.location.href = '/'
          return
        }
        if (cancelled) return

        const subs = data.data.subscriptions || []
        setSubscriptions(subs)
        setAvailableAccounts(data.data.available_accounts || [])
        const targetSub = (currentSubId ? subs.find((item) => item.subscriptionId === currentSubId) : null) || data.data.current || subs[0]
        if (targetSub?.subscriptionId) {
          setCurrentSubId(targetSub.subscriptionId)
        } else {
          setNoNumberMode(true)
        }
      } catch {
        // Login redirects are handled by the backend; keep the loader fallback silent here.
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void init()
    return () => {
      cancelled = true
    }
  }, [accountId, currentSubId, setAvailableAccounts, setCurrentSubId, setLoading, setNoNumberMode, setSubscriptions])

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
        if (!cancelled) setPlans(data.status === 'success' ? (data.plans || []).slice().sort((a, b) => a.price - b.price) : [])
      } catch {
        if (!cancelled) setPlans([])
      } finally {
        if (!cancelled) setPlansLoading(false)
      }
    }

    void fetchBalance()
    void fetchPlans()
    if (!noNumberMode) {
      void fetchInbox(false, showAlert)
      void fetchHistory(false, true, showAlert)
    }
    resetCart()
    resetHistory()
    if (category === 'CMN' && !noNumberMode) void checkCmnEligibility()

    return () => {
      cancelled = true
    }
    // fetchInbox/fetchHistory/checkCmnEligibility intentionally use current UI cache state;
    // including them would retrigger this initialization effect on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, category, currentSubId, noNumberMode])
}
