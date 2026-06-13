import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/lib/auth-context'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import SignIn from '@/pages/SignIn'
import Chat from '@/pages/Chat'
import { signOut } from '@/lib/auth'
import { listThreads, createThread, ChatThread } from '@/lib/api'
import { Plus, MessageSquare } from 'lucide-react'

function Home() {
  const { user } = useAuth()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadThreads() {
      const threads = await listThreads()
      setThreads(threads)
      setLoading(false)
    }
    loadThreads()
  }, [])

  const handleSignOut = () => {
    signOut()
    window.location.href = '/signin'
  }

  async function handleNewChat() {
    const thread = await createThread('New Chat')
    if (thread) {
      setThreads([thread, ...threads])
      window.location.href = `/chat/${thread.id}`
    }
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
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl font-bold mb-2">Conversations</h2>
              <p className="text-foreground/60">Chat with your documents</p>
            </div>
            <button
              onClick={handleNewChat}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2"
            >
              <Plus className="w-5 h-5" />
              New Chat
            </button>
          </div>

          {loading ? (
            <div className="text-center text-foreground/60">Loading conversations...</div>
          ) : threads.length === 0 ? (
            <div className="text-center">
              <MessageSquare className="w-12 h-12 mx-auto text-foreground/20 mb-4" />
              <p className="text-foreground/60 mb-4">No conversations yet</p>
              <button
                onClick={handleNewChat}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
              >
                Start Your First Chat
              </button>
            </div>
          ) : (
            <div className="grid gap-4">
              {threads.map((thread) => (
                <a
                  key={thread.id}
                  href={`/chat/${thread.id}`}
                  className="p-4 border border-border rounded-lg hover:bg-secondary/50 transition-colors"
                >
                  <h3 className="font-semibold mb-1">{thread.title || 'Untitled'}</h3>
                  <p className="text-sm text-foreground/60">
                    {new Date(thread.updated_at).toLocaleDateString()}
                  </p>
                </a>
              ))}
            </div>
          )}
        </div>
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
          <Route
            path="/chat/:threadId"
            element={
              <ProtectedRoute>
                <Chat />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
