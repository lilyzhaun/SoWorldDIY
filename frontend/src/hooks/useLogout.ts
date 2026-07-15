import { useCallback } from 'react'

import { apiFetch } from '@/api/client'
import { toUserFacingApiError } from '@/utils'

type ShowAlert = (text: string, title?: string) => void

type LogoutNavigate = (url: string) => void

async function messageFromFailedResponse(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { message?: string }
    if (typeof body.message === 'string' && body.message.trim()) return body.message.trim()
  } catch {
    void 0
  }
  if (response.status === 403) return '没有权限执行此操作'
  if (response.status >= 500) return '服务暂时不可用，请稍后再试'
  return '退出失败'
}

export async function performLogout(
  accountId: string,
  showAlert: ShowAlert,
  navigate: LogoutNavigate = (url) => {
    window.location.href = url
  },
): Promise<void> {
  const formData = new FormData()
  if (accountId) formData.append('account_id', accountId)
  try {
    const response = await apiFetch('/logout', { method: 'POST', body: formData })
    if (!response.ok) {
      showAlert(await messageFromFailedResponse(response), '错误')
      return
    }
    navigate(response.redirected && response.url ? response.url : '/')
  } catch (error: unknown) {
    showAlert(toUserFacingApiError(error, '退出失败'), '错误')
  }
}

export function useLogout(accountId: string, showAlert: ShowAlert): () => void {
  return useCallback(() => {
    void performLogout(accountId, showAlert)
  }, [accountId, showAlert])
}
