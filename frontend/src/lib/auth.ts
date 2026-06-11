import { env } from './env'

const TOKEN_KEY = 'auth_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export async function signInWithEmail(email: string) {
  try {
    const response = await fetch(`${env.apiBaseUrl}/auth/token?email=${encodeURIComponent(email)}`, {
      method: 'POST',
    })

    if (!response.ok) {
      return { data: null, error: { message: 'Failed to get token' } }
    }

    const { access_token } = await response.json()
    setToken(access_token)
    return { data: { token: access_token }, error: null }
  } catch (error) {
    return { data: null, error: { message: error instanceof Error ? error.message : 'Sign in failed' } }
  }
}

export function signOut(): void {
  clearToken()
}

export function isAuthenticated(): boolean {
  return !!getToken()
}
