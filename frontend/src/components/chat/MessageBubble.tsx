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
        className={`max-w-2xl px-4 py-3 rounded-2xl ${
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted text-foreground'
        }`}
      >
        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{content}</p>
        {isStreaming && (
          <span className="inline-block w-2 h-4 ml-2 bg-current animate-pulse" />
        )}
      </div>
    </div>
  )
}
