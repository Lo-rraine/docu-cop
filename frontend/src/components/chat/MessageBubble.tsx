interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
}

export default function MessageBubble({ role, content, isStreaming }: MessageBubbleProps) {
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-2xl px-4 py-3 rounded-lg ${
          isUser
            ? 'bg-primary text-primary-foreground rounded-br-none'
            : 'bg-secondary text-secondary-foreground rounded-bl-none'
        }`}
      >
        <p className="text-sm whitespace-pre-wrap break-words">{content}</p>
        {isStreaming && <span className="inline-block w-1 h-4 ml-1 bg-current animate-pulse" />}
      </div>
    </div>
  )
}
