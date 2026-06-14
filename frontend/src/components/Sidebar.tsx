import { useState, useEffect, useCallback } from 'react'
import { Plus, LogOut, RotateCcw } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '@/lib/auth-context'
import { listThreads, createThread, ChatThread } from '@/lib/api'
import { signOut } from '@/lib/auth'

// Global event emitter for thread updates
const threadUpdateEmitter = new EventTarget()
export const ThreadUpdateEvent = new Event('threadUpdate')

export function notifyThreadUpdate() {
  threadUpdateEmitter.dispatchEvent(ThreadUpdateEvent)
}

export default function Sidebar() {
  const { user } = useAuth()
  const location = useLocation()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadThreads()

    // Listen for thread updates
    threadUpdateEmitter.addEventListener('threadUpdate', loadThreads)
    return () => {
      threadUpdateEmitter.removeEventListener('threadUpdate', loadThreads)
    }
  }, [])

  const loadThreads = useCallback(async () => {
    setLoading(true)
    const threads = await listThreads()
    setThreads(threads)
    setLoading(false)
  }, [])

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

  const isActive = (threadId: string) => location.pathname === `/chat/${threadId}`

  return (
    <div className="w-64 border-r border-border/50 bg-background flex flex-col shadow-sm">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border/50">
        <h1 className="text-base font-semibold tracking-tight text-foreground">Document Copilot</h1>
        <p className="text-xs text-foreground/50 mt-1.5 font-medium">Chat with SEC filings</p>
      </div>

      {/* New Chat Button */}
      <button
        onClick={handleNewChat}
        className="mx-4 mt-4 flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 active:bg-primary/85 transition-colors duration-150 text-sm font-medium shadow-sm hover:shadow-md"
      >
        <Plus className="w-4 h-4" />
        New chat
      </button>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <p className="text-xs font-semibold text-foreground/50 uppercase tracking-widest mb-4 block">
          Conversations
        </p>

        {loading ? (
          <div className="space-y-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-8 bg-muted/40 rounded-lg" />
            ))}
          </div>
        ) : threads.length === 0 ? (
          <p className="text-xs text-foreground/40 text-center py-8">No conversations yet</p>
        ) : (
          <div className="space-y-1.5">
            {threads.map((thread) => (
              <a
                key={thread.id}
                href={`/chat/${thread.id}`}
                className={`block px-3 py-2.5 rounded-lg text-sm transition-all duration-150 truncate ${
                  isActive(thread.id)
                    ? 'bg-primary/10 text-foreground font-medium shadow-sm'
                    : 'text-foreground/70 hover:bg-muted/60 hover:text-foreground'
                }`}
                title={thread.title || 'Untitled'}
              >
                {thread.title || 'Untitled'}
              </a>
            ))}
          </div>
        )}
      </div>

      {/* User Section */}
      <div className="px-4 py-4 border-t border-border/50 space-y-3">
        <p className="text-xs text-foreground/50 font-medium truncate">{user?.email}</p>
        <button
          onClick={handleSignOut}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm text-foreground/70 hover:text-foreground hover:bg-muted/60 rounded-lg transition-colors duration-150"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </div>
  )
}
