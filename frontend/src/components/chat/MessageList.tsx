import { useEffect, useRef } from 'react'
import type { ChatMessage, CitationPayload } from '@/lib/chat'
import MessageBubble from './MessageBubble'
import { PipelineStatus } from './PipelineStatus'

interface MessageListProps {
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  selectedCitationIndex: number | null
  onSelectCitation: (c: CitationPayload) => void
  pipelineStatus: string | null
}

export default function MessageList({
  messages,
  isLoading,
  error,
  selectedCitationIndex,
  onSelectCitation,
  pipelineStatus,
}: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const lastMessage = messages[messages.length - 1]
  const showPipelineStatus = isLoading && (!lastMessage || lastMessage.role !== 'user' || !lastMessage.content)

  return (
    <div className='flex-1 overflow-y-auto p-6 space-y-4'>
      {messages.length === 0 && (
        <div className='h-full flex items-center justify-center'>
          <div className='text-center max-w-2xl'>
            <h2 className='text-3xl font-semibold text-foreground mb-2'>
              Start a conversation
            </h2>
            <p className='text-foreground/60'>
              Choose an existing thread from the sidebar or ask a question about SEC filings.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className='mx-auto max-w-2xl p-4 bg-destructive/10 border border-destructive/20 rounded-lg'>
          <p className='text-sm text-destructive font-medium'>Error</p>
          <p className='text-sm text-destructive/80 mt-1'>{error}</p>
        </div>
      )}

      {showPipelineStatus && <PipelineStatus status={pipelineStatus} />}

      {messages.map((message, index) => (
        <MessageBubble
          key={index}
          message={message}
          isStreaming={isLoading && index === messages.length - 1}
          selectedCitationIndex={selectedCitationIndex}
          onSelectCitation={onSelectCitation}
        />
      ))}

      <div ref={endRef} />
    </div>
  )
}
