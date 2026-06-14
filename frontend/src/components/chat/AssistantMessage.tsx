import { Copy, Check } from 'lucide-react'
import { useState } from 'react'
import type { ChatMessage, CitationPayload } from '@/lib/chat'
import { Button } from '@/components/ui/button'
import { AssistantMarkdown } from './AssistantMarkdown'
import { CitationChip } from './CitationChip'

interface AssistantMessageProps {
  message: ChatMessage
  isStreaming: boolean
  selectedCitationIndex: number | null
  onSelectCitation: (c: CitationPayload) => void
}

export function AssistantMessage({
  message,
  isStreaming,
  selectedCitationIndex,
  onSelectCitation,
}: AssistantMessageProps) {
  const [copied, setCopied] = useState(false)
  const citations = message.citations ?? []

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className='space-y-3'>
      <div className='space-y-2'>
        <div className='flex items-start gap-3'>
          <div className='flex-1 text-sm leading-relaxed'>
            {message.content ? (
              <AssistantMarkdown
                content={message.content}
                citations={citations}
                selectedIndex={selectedCitationIndex}
                onSelect={onSelectCitation}
              />
            ) : null}
            {isStreaming && message.content && (
              <span className='inline-block h-4 w-2 translate-y-0.5 animate-pulse rounded-sm bg-foreground' />
            )}
          </div>
          <Button
            variant='ghost'
            size='icon'
            onClick={handleCopy}
            disabled={isStreaming || !message.content}
            className='mt-0.5 flex-shrink-0 hover:bg-foreground/10 transition-colors duration-150'
          >
            {copied ? <Check className='h-4 w-4 text-green-600 dark:text-green-400' /> : <Copy className='h-4 w-4' />}
          </Button>
        </div>

        {!isStreaming && citations.length === 0 && message.content && (
          <p className='text-xs text-foreground/50 italic pt-1'>
            No filing evidence was found to support this answer.
          </p>
        )}
      </div>

      {!isStreaming && citations.length > 0 && (
        <div className='flex flex-wrap gap-2 pt-2'>
          {citations.map((citation) => (
            <CitationChip
              key={`${citation.chunk_id}-${citation.citation_index}`}
              citation={citation}
              selected={selectedCitationIndex === citation.citation_index}
              onSelect={onSelectCitation}
            />
          ))}
        </div>
      )}
    </div>
  )
}
