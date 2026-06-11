interface FetchOptions extends RequestInit {
  headers?: Record<string, string>
}

export async function fetchWithAuth(url: string, options: FetchOptions = {}) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers,
  })

  return response
}
