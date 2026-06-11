import { env } from './env'

export async function register(email: string, password: string) {
  try {
    const response = await fetch(`${env.apiBaseUrl}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    })

    if (!response.ok) {
      const error = await response.json()
      return { data: null, error: { message: error.detail || 'Registration failed' } }
    }

    const data = await response.json()
    return { data: { email: data.email }, error: null }
  } catch (error) {
    return { data: null, error: { message: error instanceof Error ? error.message : 'Registration failed' } }
  }
}

export async function login(email: string, password: string) {
  try {
    const response = await fetch(`${env.apiBaseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    })

    if (!response.ok) {
      const error = await response.json()
      return { data: null, error: { message: error.detail || 'Login failed' } }
    }

    const data = await response.json()
    return { data: { email: data.email }, error: null }
  } catch (error) {
    return { data: null, error: { message: error instanceof Error ? error.message : 'Login failed' } }
  }
}

export async function logout() {
  try {
    const response = await fetch(`${env.apiBaseUrl}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    })

    return response.ok
  } catch (error) {
    console.error('Logout failed:', error)
    return false
  }
}

export function signOut(): void {
  logout()
}

export async function isAuthenticated(): Promise<boolean> {
  try {
    const response = await fetch(`${env.apiBaseUrl}/me`, {
      credentials: 'include',
    })
    return response.ok
  } catch (error) {
    return false
  }
}
