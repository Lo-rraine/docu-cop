import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { streamChat, ChatMessage, CitationPayload } from '@/lib/chat'
import { getThread } from '@/lib/api'
import { notifyThreadUpdate } from '@/components/Sidebar'
import MessageList from '@/components/chat/MessageList'
import ChatInput from '@/components/chat/ChatInput'
import { SourcePassageSheet } from '@/components/chat/SourcePassageSheet'
import { ProcessingProgress } from '@/components/chat/ProcessingProgress'

export default function Chat() {
  const { threadId } = useParams<{ threadId: string }>()
  const navigate = useNavigate()

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCitation, setSelectedCitation] = useState<CitationPayload | null>(null)
  const [pipelineStatus, setPipelineStatus] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Load existing messages when thread changes
  useEffect(() => {
    if (!threadId) {
      navigate('/')
      return
    }

    async function loadThread() {
      setIsLoadingHistory(true)
      try {
        const thread = await getThread(threadId)
        if (thread) {
          // Convert ThreadMessage to ChatMessage format
          const messages: ChatMessage[] = thread.messages.map((msg) => ({
            id: msg.id,
            role: msg.role as 'user' | 'assistant',
            content: msg.content,
            citations: msg.citations && msg.citations.length > 0
              ? msg.citations.map((c) => ({
                  citation_index: c.citation_index,
                  chunk_id: c.chunk_id,
                  excerpt: c.excerpt,
                  ticker: c.ticker,
                  filing_type: c.filing_type,
                  filing_year: c.filing_year,
                  heading: c.heading,
                }))
              : [],
          }))
          setMessages(messages)
        } else {
          setError('Failed to load thread')
        }
      } catch (err) {
        console.error('Error loading thread:', err)
        setError(err instanceof Error ? err.message : 'Failed to load thread')
      }
      setIsLoadingHistory(false)
    }

    loadThread()
  }, [threadId, navigate])

  if (!threadId) {
    navigate('/')
    return null
  }

  async function handleSendMessage(content: string) {
    if (!content.trim()) return

    setError(null)
    setSelectedCitation(null)
    setPipelineStatus(null)

    const userMessage: ChatMessage = { role: 'user', content }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setIsLoading(true)

    // Add empty assistant message placeholder to show processing progress
    const assistantMessage: ChatMessage = { role: 'assistant', content: '', citations: [] }
    setMessages([...updatedMessages, assistantMessage])
    let assistantMessageAdded = false

    abortControllerRef.current = new AbortController()

    try {
      const generator = streamChat(threadId, updatedMessages, abortControllerRef.current.signal)
      let isFirstMessage = updatedMessages.filter(m => m.role === 'user').length === 1

      for await (const event of generator) {
        if (event.type === 'text') {
          // Add placeholder message on first text content
          if (!assistantMessageAdded) {
            const assistantMessage: ChatMessage = { role: 'assistant', content: event.data, citations: [] }
            setMessages([...updatedMessages, assistantMessage])
            assistantMessageAdded = true
          } else {
            // Append to existing message
            setMessages((prev) => {
              const last = { ...prev[prev.length - 1] }
              last.content += event.data
              return [...prev.slice(0, -1), last]
            })
          }
        } else if (event.type === 'data') {
          const payload = event.data as Record<string, unknown>
          if (payload.type === 'citation') {
            const citation = (payload.data as CitationPayload)
            setMessages((prev) => {
              const last = { ...prev[prev.length - 1] }
              last.citations = [...(last.citations ?? []), citation]
              return [...prev.slice(0, -1), last]
            })
          } else if (payload.type === 'status') {
            setPipelineStatus((payload.message as string) ?? null)
          }
        } else if (event.type === 'error') {
          setError(String(event.data))
          setMessages((prev) => prev.slice(0, -1))
        } else if (event.type === 'done') {
          setIsLoading(false)
          setPipelineStatus(null)

          // Refresh sidebar thread list after first message (title auto-generated)
          if (isFirstMessage) {
            notifyThreadUpdate()
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // Remove any added messages on abort
        if (assistantMessageAdded) {
          setMessages((prev) => prev.slice(0, -1))
        }
      } else {
        setError(err instanceof Error ? err.message : 'An error occurred')
        // Remove any added messages on error
        if (assistantMessageAdded) {
          setMessages((prev) => prev.slice(0, -1))
        }
      }
      setIsLoading(false)
      setPipelineStatus(null)
    }
  }

  function handleCancel() {
    abortControllerRef.current?.abort()
    setIsLoading(false)
    setPipelineStatus(null)
    setMessages((prev) => prev.slice(0, -1))
  }

  return (
    <main className='flex-1 flex flex-col overflow-hidden'>
      <MessageList
        messages={messages}
        isLoading={isLoading}
        isLoadingHistory={isLoadingHistory}
        error={error}
        selectedCitationIndex={selectedCitation?.citation_index ?? null}
        onSelectCitation={setSelectedCitation}
        pipelineStatus={pipelineStatus}
      />
      <ChatInput
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        onCancel={handleCancel}
        disabled={!threadId}
      />
      <SourcePassageSheet
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </main>
  )
}
