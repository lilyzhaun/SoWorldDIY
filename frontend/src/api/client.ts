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

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const method = (init.method || 'GET').toUpperCase()
  const headers = method === 'GET' || method === 'HEAD' ? init.headers : withCsrfHeaders(init.headers)
  return fetch(input, { ...init, headers })
}

export async function apiGet<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(url, init)
  return response.json() as Promise<T>
}

export async function apiPostJson<T>(url: string, body: unknown, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  const response = await apiFetch(url, {
    ...init,
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  return response.json() as Promise<T>
}
