import { useState, useRef, useEffect } from 'react'
import { Send, Square } from 'lucide-react'

interface ChatInputProps {
  onSendMessage: (content: string) => void
  isLoading: boolean
  onCancel: () => void
  disabled?: boolean
}

export default function ChatInput({ onSendMessage, isLoading, onCancel, disabled }: ChatInputProps) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px'
    }
  }, [input])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || isLoading || disabled) return

    onSendMessage(input)
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t border-border/50 px-6 py-4 bg-background shadow-lg shadow-black/5"
    >
      <div className="flex gap-3 max-w-4xl mx-auto items-end">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about SEC filings..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSubmit(e as unknown as React.FormEvent)
            }
          }}
          disabled={isLoading || disabled}
          className="flex-1 resize-none rounded-xl border border-input/80 bg-background px-4 py-3 text-sm placeholder:text-foreground/45 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed max-h-48 shadow-sm"
        />
        {isLoading ? (
          <button
            type="button"
            onClick={onCancel}
            className="flex-shrink-0 w-10 h-10 rounded-full bg-destructive text-destructive-foreground hover:bg-destructive/90 active:bg-destructive/80 transition-colors duration-150 flex items-center justify-center shadow-md hover:shadow-lg"
            title="Cancel"
          >
            <Square className="w-5 h-5" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim() || disabled}
            className="flex-shrink-0 w-10 h-10 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 active:bg-primary/80 transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-md hover:shadow-lg"
            title="Send (Shift+Enter for new line)"
          >
            <Send className="w-5 h-5" />
          </button>
        )}
      </div>
    </form>
  )
}
