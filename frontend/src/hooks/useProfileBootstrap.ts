import { useEffect, type Dispatch, type SetStateAction } from 'react'

import { apiFetch } from '@/api/client'
import type { AvailableAccount, ProfileResponse, Subscription } from '@/types'
import { getApiUrl } from '@/utils/mainPage'
import { selectProfileSubscription } from '@/utils/profileBootstrap'

type ProfileBootstrapDeps = {
  readonly accountId: string
  readonly currentSubId: string
  readonly setCurrentSubId: Dispatch<SetStateAction<string>>
  readonly setNoNumberMode: Dispatch<SetStateAction<boolean>>
  readonly setLoading: Dispatch<SetStateAction<boolean>>
  readonly setSubscriptions: Dispatch<SetStateAction<Subscription[]>>
  readonly setAvailableAccounts: Dispatch<SetStateAction<AvailableAccount[]>>
}

export function useProfileBootstrap(deps: ProfileBootstrapDeps): void {
  const {
    accountId,
    currentSubId,
    setCurrentSubId,
    setNoNumberMode,
    setLoading,
    setSubscriptions,
    setAvailableAccounts,
  } = deps

  useEffect(() => {
    let cancelled = false
    const init = async (): Promise<void> => {
      try {
        const apiUrl = getApiUrl(`/api/profile?_t=${Date.now()}`, accountId)
        const response = await apiFetch(apiUrl, { headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' } })
        const contentType = response.headers.get('content-type')
        if (response.status === 401 || response.status === 409) {
          window.location.href = '/?session=expired'
          return
        }
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
        const selection = selectProfileSubscription(subs, data.data.current, currentSubId)
        if (selection.noNumberMode) {
          setNoNumberMode(true)
        } else {
          setCurrentSubId(selection.currentSubId)
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
}
