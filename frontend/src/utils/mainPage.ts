export function getAccountIdFromPathname(pathname: string): string {
  const pathParts = pathname.split('/')
  const mainIdx = pathParts.indexOf('main')
  return (mainIdx >= 0 ? pathParts[mainIdx + 1] : '') ?? ''
}

export function getApiUrl(endpoint: string, accountId: string): string {
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  if (!accountId) return normalizedEndpoint
  const separator = normalizedEndpoint.includes('?') ? '&' : '?'
  return `${normalizedEndpoint}${separator}account_id=${accountId}`
}

export function stripHtml(input: string): string {
  return input.replace(/<[^>]+>/g, '')
}

export function formatStatus(status?: string): { text: string; color: string } {
  if (status === 'ACTIVE') return { text: '正常', color: '#10b981' }
  if (status === 'PREACTIVE') return { text: '待激活', color: '#f59e0b' }
  if (status === 'SUSPENDED' || status === 'TERMINATED') return { text: '已停用', color: '#ef4444' }
  return { text: status || '--', color: '#718096' }
}

export function normalizeUnit(unit?: string): string {
  const raw = (unit || '').toLowerCase()
  if (raw === 'megabytes') return 'MB'
  if (raw === 'minutes') return '分钟'
  if (raw === 'days') return '天'
  return unit || ''
}

export function getIsoTime(date: Date, isEnd = false): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const time = isEnd ? '23:59:59.999' : '00:00:00.000'
  return `${y}-${m}-${d}T${time}`
}
