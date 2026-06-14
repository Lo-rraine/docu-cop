import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { CitationPayload } from '@/lib/chat'
import { CitationMarker } from './CitationMarker'

interface AssistantMarkdownProps {
  content: string
  citations: CitationPayload[]
  selectedIndex: number | null
  onSelect: (c: CitationPayload) => void
}

function withCitationLinks(text: string, citations: CitationPayload[]): string {
  // Replace [N] with [N](#citation-N) only for valid indices
  const validIndices = new Set(citations.map((c) => c.citation_index))
  return text.replace(/\[(\d+)\]/g, (match, n) =>
    validIndices.has(Number(n)) ? `[${n}](#citation-${n})` : match
  )
}

export function AssistantMarkdown({
  content,
  citations,
  selectedIndex,
  onSelect,
}: AssistantMarkdownProps) {
  const linkifiedContent = withCitationLinks(content, citations)

  const citationMap = new Map(citations.map((c) => [c.citation_index, c]))

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => {
          if (href?.startsWith('#citation-')) {
            const indexStr = href.replace('#citation-', '')
            const index = Number(indexStr)
            const citation = citationMap.get(index)
            if (citation) {
              return (
                <CitationMarker
                  index={index}
                  selected={selectedIndex === index}
                  onSelect={() => onSelect(citation)}
                />
              )
            }
          }
          // Regular link
          return (
            <a href={href} className='text-primary hover:underline transition-colors duration-150 font-medium'>
              {children}
            </a>
          )
        },
        p: ({ children }) => <p className='whitespace-pre-wrap mb-1'>{children}</p>,
        code: ({ inline, children }) => {
          if (inline) {
            return <code className='bg-muted/70 px-2 py-0.5 rounded text-xs font-mono text-foreground/90'>{children}</code>
          }
          return (
            <pre className='bg-muted/60 p-4 rounded-lg overflow-x-auto my-3 border border-border/30'>
              <code className='text-xs font-mono leading-relaxed text-foreground'>{children}</code>
            </pre>
          )
        },
        ul: ({ children }) => <ul className='list-disc ml-5 my-2 space-y-1'>{children}</ul>,
        ol: ({ children }) => <ol className='list-decimal ml-5 my-2 space-y-1'>{children}</ol>,
        li: ({ children }) => <li className='text-sm'>{children}</li>,
        h1: ({ children }) => <h1 className='text-lg font-semibold my-3 mt-4 text-foreground'>{children}</h1>,
        h2: ({ children }) => <h2 className='text-base font-semibold my-2.5 mt-3.5 text-foreground'>{children}</h2>,
        h3: ({ children }) => <h3 className='text-sm font-semibold my-2 text-foreground'>{children}</h3>,
        blockquote: ({ children }) => (
          <blockquote className='border-l-4 border-primary/50 pl-4 italic my-3 text-foreground/80 bg-muted/30 py-2 rounded-r'>
            {children}
          </blockquote>
        ),
        table: ({ children }) => (
          <div className='overflow-x-auto my-3'>
            <table className='border-collapse border border-border/50 text-sm'>{children}</table>
          </div>
        ),
        td: ({ children }) => (
          <td className='border border-border/50 p-2 text-foreground/90'>{children}</td>
        ),
        th: ({ children }) => (
          <th className='border border-border/50 p-2 bg-muted/60 font-semibold text-foreground'>{children}</th>
        ),
      }}
    >
      {linkifiedContent}
    </ReactMarkdown>
  )
}
