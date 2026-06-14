import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { streamChat, ChatMessage, CitationPayload } from '@/lib/chat'
import MessageList from '@/components/chat/MessageList'
import ChatInput from '@/components/chat/ChatInput'
import { SourcePassageSheet } from '@/components/chat/SourcePassageSheet'

export default function Chat() {
  const { threadId } = useParams<{ threadId: string }>()
  const navigate = useNavigate()

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedCitation, setSelectedCitation] = useState<CitationPayload | null>(null)
  const [pipelineStatus, setPipelineStatus] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

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

    const assistantMessage: ChatMessage = { role: 'assistant', content: '', citations: [] }
    setMessages([...updatedMessages, assistantMessage])

    abortControllerRef.current = new AbortController()

    try {
      const generator = streamChat(threadId, updatedMessages, abortControllerRef.current.signal)

      for await (const event of generator) {
        if (event.type === 'text') {
          setMessages((prev) => {
            const last = { ...prev[prev.length - 1] }
            last.content += event.data
            return [...prev.slice(0, -1), last]
          })
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
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setMessages((prev) => prev.slice(0, -1))
      } else {
        setError(err instanceof Error ? err.message : 'An error occurred')
        setMessages((prev) => prev.slice(0, -1))
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
