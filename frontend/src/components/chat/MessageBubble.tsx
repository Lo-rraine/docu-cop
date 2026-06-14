import type { ChatMessage, CitationPayload } from '@/lib/chat'
import { AssistantMessage } from './AssistantMessage'

interface MessageBubbleProps {
  message: ChatMessage
  isStreaming?: boolean
  selectedCitationIndex: number | null
  onSelectCitation: (c: CitationPayload) => void
}

export default function MessageBubble({
  message,
  isStreaming,
  selectedCitationIndex,
  onSelectCitation,
}: MessageBubbleProps) {
  const isUser = message.role === 'user'

  if (message.role === 'assistant') {
    return (
      <div className='flex justify-start'>
        <div className='max-w-2xl px-4 py-3 rounded-2xl bg-muted text-foreground'>
          <AssistantMessage
            message={message}
            isStreaming={isStreaming ?? false}
            selectedCitationIndex={selectedCitationIndex}
            onSelectCitation={onSelectCitation}
          />
        </div>
      </div>
    )
  }

  return (
    <div className='flex justify-end'>
      <div className='max-w-2xl px-4 py-3 rounded-2xl rounded-br-none bg-primary text-primary-foreground'>
        <p className='text-sm leading-relaxed whitespace-pre-wrap break-words'>
          {message.content}
        </p>
      </div>
    </div>
  )
}
