import { ApiHttpError } from '@/api/client'

function messageFromBody(bodyJson: unknown): string | undefined {
  if (!bodyJson || typeof bodyJson !== 'object') return undefined
  const record = bodyJson as { message?: unknown; detail?: unknown }
  if (typeof record.message === 'string' && record.message.trim()) return record.message.trim()
  if (typeof record.detail === 'string' && record.detail.trim()) return record.detail.trim()
  return undefined
}

export function toUserFacingApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiHttpError) {
    const fromBody = messageFromBody(error.bodyJson)
    if (fromBody) return fromBody
    if (error.status === 401) return '登录已失效，请重新登录'
    if (error.status === 403) return '没有权限执行此操作'
    if (error.status === 404) return '请求的资源不存在'
    if (error.status === 429) return '请求过于频繁，请稍后再试'
    if (error.status >= 500) return '服务暂时不可用，请稍后再试'
    return fallback
  }
  if (error instanceof Error && error.message.trim()) return error.message
  return fallback
}

export function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }

  return String(error)
}
