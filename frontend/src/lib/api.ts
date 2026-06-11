import { fetchWithAuth } from './http'
import { env } from './env'

export interface User {
  id: string
  email: string
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await fetchWithAuth(`${env.apiBaseUrl}/me`)

    if (!response.ok) {
      if (response.status === 401) {
        return null
      }
      throw new Error('Failed to fetch user')
    }

    return response.json()
  } catch (error) {
    console.error('Error fetching current user:', error)
    return null
  }
}
