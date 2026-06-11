import { ReactNode, createContext, useContext, useEffect, useState, useCallback } from 'react'
import { isAuthenticated } from './auth'
import { getCurrentUser } from './api'

interface User {
  id: string
  email: string
}

interface AuthContextType {
  isAuthenticated: boolean
  user: User | null
  loading: boolean
  refreshAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuth, setIsAuth] = useState(false)
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const checkAuth = useCallback(async () => {
    if (isAuthenticated()) {
      const userData = await getCurrentUser()
      setUser(userData)
      setIsAuth(true)
    } else {
      setIsAuth(false)
      setUser(null)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  return (
    <AuthContext.Provider value={{ isAuthenticated: isAuth, user, loading, refreshAuth: checkAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
