import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '@/lib/auth'
import { useAuth } from '@/lib/auth-context'

export default function SignIn() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { refreshAuth } = useAuth()

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const { error: loginError } = await login(email, password)

    if (loginError) {
      setError(loginError.message)
      setLoading(false)
    } else {
      await refreshAuth()
      navigate('/')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground mb-2">Document Copilot</h1>
          <p className="text-sm text-foreground/60 font-medium">Sign in to your account</p>
        </div>

        <form onSubmit={handleSignIn} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-foreground mb-2">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="w-full px-4 py-3 border border-input/80 rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 text-sm placeholder:text-foreground/45 transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              disabled={loading}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-foreground mb-2">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full px-4 py-3 border border-input/80 rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 text-sm placeholder:text-foreground/45 transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              disabled={loading}
            />
          </div>

          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive font-medium">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !email || !password}
            className="w-full px-4 py-3 bg-primary text-primary-foreground rounded-lg font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary/90 active:bg-primary/80 transition-colors duration-150 mt-6 shadow-md hover:shadow-lg"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
