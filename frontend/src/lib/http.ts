import { getToken } from './auth'

interface FetchOptions extends RequestInit {
  headers?: Record<string, string>
}

export async function fetchWithAuth(url: string, options: FetchOptions = {}) {
  const token = getToken()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  return response
}
