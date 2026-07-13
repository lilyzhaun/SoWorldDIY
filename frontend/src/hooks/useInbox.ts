import { useState } from 'react'

import { apiGet } from '@/api/client'
import type { InboxMessage } from '@/types'
import { getApiUrl } from '@/utils/mainPage'

type ShowAlert = (text: string, title?: string) => void

type InboxState = {
  readonly activeInboxIndex: number | null
  readonly fetchInbox: (force: boolean, showAlert: ShowAlert) => Promise<void>
  readonly inboxLoading: boolean
  readonly inboxMessages: InboxMessage[]
  readonly inboxOpen: boolean
  readonly openInbox: (showAlert: ShowAlert) => Promise<void>
  readonly setActiveInboxIndex: (index: number | null) => void
  readonly setInboxOpen: (open: boolean) => void
}

export function useInbox(accountId: string): InboxState {
  const [inboxOpen, setInboxOpen] = useState(false)
  const [inboxLoading, setInboxLoading] = useState(false)
  const [inboxMessages, setInboxMessages] = useState<InboxMessage[]>([])
  const [activeInboxIndex, setActiveInboxIndex] = useState<number | null>(null)

  const fetchInbox = async (force: boolean, showAlert: ShowAlert): Promise<void> => {
    if (!force && inboxMessages.length > 0) return
    setInboxLoading(true)
    try {
      const url = getApiUrl('/api/inbox', accountId)
      const data = await apiGet<{ status?: string; messages?: InboxMessage[] }>(url)
      if (data.status === 'success') setInboxMessages(data.messages || [])
      else if (inboxOpen) showAlert('加载失败')
    } catch {
      if (inboxOpen) showAlert('加载失败')
    } finally {
      setInboxLoading(false)
    }
  }

  const openInbox = async (showAlert: ShowAlert): Promise<void> => {
    setInboxOpen(true)
    if (inboxMessages.length === 0) await fetchInbox(true, showAlert)
  }

  return {
    activeInboxIndex,
    fetchInbox,
    inboxLoading,
    inboxMessages,
    inboxOpen,
    openInbox,
    setActiveInboxIndex,
    setInboxOpen,
  }
}
