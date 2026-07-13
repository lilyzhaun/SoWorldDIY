import { useState, type Dispatch, type SetStateAction } from 'react'

import { apiGet } from '@/api/client'
import type { AvailableAccount, ProfileResponse, Subscription } from '@/types'
import { getApiUrl } from '@/utils/mainPage'

type ShowAlert = (text: string, title?: string) => void

type ProfileRefreshOptions = {
  readonly accountId: string
  readonly setAvailableAccounts: Dispatch<SetStateAction<AvailableAccount[]>>
  readonly setSubscriptions: Dispatch<SetStateAction<Subscription[]>>
  readonly showAlert: ShowAlert
}

export const PROFILE_REFRESH_COMPLETION_DELAY_MS = 500

export function useProfileRefresh({
  accountId,
  setAvailableAccounts,
  setSubscriptions,
  showAlert,
}: ProfileRefreshOptions) {
  const [refreshingUsage, setRefreshingUsage] = useState(false)

  const refreshProfileData = async (): Promise<void> => {
    setRefreshingUsage(true)
    try {
      const url = getApiUrl(`/api/profile?refresh=true&_t=${Date.now()}`, accountId)
      const data = await apiGet<ProfileResponse>(url)
      if (data.status === 'success') {
        setSubscriptions(data.data.subscriptions || [])
        setAvailableAccounts(data.data.available_accounts || [])
      } else {
        showAlert('刷新失败')
      }
    } catch {
      showAlert('网络连接失败')
    } finally {
      window.setTimeout(() => setRefreshingUsage(false), PROFILE_REFRESH_COMPLETION_DELAY_MS)
    }
  }

  return { refreshingUsage, refreshProfileData }
}
