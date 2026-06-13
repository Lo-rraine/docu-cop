import { useState, useEffect } from 'react'
import { Plus, LogOut } from 'lucide-react'
import { useAuth } from '@/lib/auth-context'
import { listThreads, createThread, ChatThread } from '@/lib/api'
import { signOut } from '@/lib/auth'

export default function Sidebar() {
  const { user } = useAuth()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadThreads()
  }, [])

  async function loadThreads() {
    const threads = await listThreads()
    setThreads(threads)
    setLoading(false)
  }

  async function handleNewChat() {
    const thread = await createThread('New Chat')
    if (thread) {
      setThreads([thread, ...threads])
      window.location.href = `/chat/${thread.id}`
    }
  }

  function handleSignOut() {
    signOut()
    window.location.href = '/signin'
  }

  return (
    <div className="w-64 border-r border-border bg-background flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <h1 className="text-lg font-semibold">Document Copilot</h1>
        <p className="text-xs text-foreground/50 mt-1">Chat with SEC filings</p>
      </div>

      {/* New Chat Button */}
      <button
        onClick={handleNewChat}
        className="m-4 flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
      >
        <Plus className="w-4 h-4" />
        New chat
      </button>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto px-4 py-2">
        <p className="text-xs font-medium text-foreground/50 uppercase tracking-wide mb-3">
          Conversations
        </p>

        {loading ? (
          <p className="text-xs text-foreground/40">Loading...</p>
        ) : threads.length === 0 ? (
          <p className="text-xs text-foreground/40">No conversations yet</p>
        ) : (
          <div className="space-y-2">
            {threads.map((thread) => (
              <a
                key={thread.id}
                href={`/chat/${thread.id}`}
                className="block px-3 py-2 rounded-lg text-sm text-foreground/70 hover:bg-muted/50 transition-colors truncate"
                title={thread.title || 'Untitled'}
              >
                {thread.title || 'Untitled'}
              </a>
            ))}
          </div>
        )}
      </div>

      {/* User Section */}
      <div className="p-4 border-t border-border space-y-2">
        <p className="text-xs text-foreground/50 truncate">{user?.email}</p>
        <button
          onClick={handleSignOut}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm text-foreground/70 hover:bg-muted/50 rounded-lg transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </div>
  )
}
