import { fetchWithAuth } from './http'
import { env } from './env'

export interface User {
  id: string
  email: string
  avatar?: string
}

export interface ChatThread {
  id: string
  title: string | null
  created_at: string
  updated_at: string
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

export async function listThreads(): Promise<ChatThread[]> {
  try {
    const response = await fetchWithAuth(`${env.apiBaseUrl}/chat/threads`)

    if (!response.ok) {
      throw new Error('Failed to fetch threads')
    }

    return response.json()
  } catch (error) {
    console.error('Error fetching threads:', error)
    return []
  }
}

export async function createThread(title?: string): Promise<ChatThread | null> {
  try {
    const response = await fetchWithAuth(`${env.apiBaseUrl}/chat/threads`, {
      method: 'POST',
      body: JSON.stringify({ title }),
    })

    if (!response.ok) {
      throw new Error('Failed to create thread')
    }

    return response.json()
  } catch (error) {
    console.error('Error creating thread:', error)
    return null
  }
}
