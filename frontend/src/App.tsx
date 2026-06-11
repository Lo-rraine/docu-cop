import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/lib/auth-context'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import SignIn from '@/pages/SignIn'
import { signOut } from '@/lib/auth'

function Home() {
  const { user } = useAuth()

  const handleSignOut = () => {
    signOut()
    window.location.href = '/signin'
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b border-border p-6 flex justify-between items-center">
        <h1 className="text-3xl font-bold">Document Copilot</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-foreground/60">{user?.email}</span>
          <button
            onClick={handleSignOut}
            className="px-4 py-2 text-sm bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/90 transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="flex-1 p-6">
        <p className="text-foreground/60">Chat with your documents coming soon...</p>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/signin" element={<SignIn />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Home />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
