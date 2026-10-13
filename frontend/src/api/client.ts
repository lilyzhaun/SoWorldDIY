export class ApiHttpError extends Error {
  readonly status: number
  readonly statusText: string
  readonly bodyText?: string
  readonly bodyJson?: unknown

  constructor(status: number, statusText: string, bodyText?: string, bodyJson?: unknown) {
    const detail = bodyText?.trim()
    super(detail ? `HTTP ${status} ${statusText}: ${detail}` : `HTTP ${status} ${statusText}`)
    this.name = 'ApiHttpError'
    this.status = status
    this.statusText = statusText
    this.bodyText = bodyText
    this.bodyJson = bodyJson
  }
}

export function getCookie(name: string, cookieSource = document.cookie): string {
  const parts = cookieSource.split(';').map((part) => part.trim())
  const prefix = `${name}=`
  const match = parts.find((part) => part.startsWith(prefix))
  return match ? decodeURIComponent(match.slice(prefix.length)) : ''
}

export function withCsrfHeaders(headers?: HeadersInit, cookieSource = document.cookie): Headers {
  const next = new Headers(headers)
  const token = getCookie('csrf_token', cookieSource)
  if (token) next.set('x-csrf-token', token)
  return next
}

export function newOperationId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const method = (init.method || 'GET').toUpperCase()
  const headers = method === 'GET' || method === 'HEAD' ? init.headers : withCsrfHeaders(init.headers)
  return fetch(input, { ...init, headers })
}

async function readErrorBody(response: Response): Promise<{ bodyText?: string; bodyJson?: unknown }> {
  const bodyText = await response.text()
  if (!bodyText) return {}
  try {
    return { bodyText, bodyJson: JSON.parse(bodyText) as unknown }
  } catch {
    return { bodyText }
  }
}

async function ensureOk(response: Response): Promise<void> {
  if (response.ok) return
  const { bodyText, bodyJson } = await readErrorBody(response)
  throw new ApiHttpError(response.status, response.statusText, bodyText, bodyJson)
}

/** Optional `init.signal` (AbortSignal) is forwarded through RequestInit. */
export async function apiGet<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(url, init)
  await ensureOk(response)
  return response.json() as Promise<T>
}

/** Optional `init.signal` (AbortSignal) is forwarded through RequestInit. */
export async function apiPostJson<T>(url: string, body: unknown, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  const response = await apiFetch(url, {
    ...init,
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  await ensureOk(response)
  return response.json() as Promise<T>
}
