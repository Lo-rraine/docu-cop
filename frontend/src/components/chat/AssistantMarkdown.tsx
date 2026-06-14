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
            <a href={href} className='text-primary hover:underline'>
              {children}
            </a>
          )
        },
        p: ({ children }) => <p className='whitespace-pre-wrap'>{children}</p>,
        code: ({ inline, children }) => {
          if (inline) {
            return <code className='bg-muted px-1 rounded text-sm'>{children}</code>
          }
          return (
            <pre className='bg-muted p-3 rounded overflow-x-auto'>
              <code>{children}</code>
            </pre>
          )
        },
        ul: ({ children }) => <ul className='list-disc ml-4'>{children}</ul>,
        ol: ({ children }) => <ol className='list-decimal ml-4'>{children}</ol>,
        h1: ({ children }) => <h1 className='text-xl font-bold my-2'>{children}</h1>,
        h2: ({ children }) => <h2 className='text-lg font-bold my-2'>{children}</h2>,
        h3: ({ children }) => <h3 className='text-base font-bold my-1'>{children}</h3>,
        blockquote: ({ children }) => (
          <blockquote className='border-l-4 border-muted-foreground pl-4 italic my-2'>
            {children}
          </blockquote>
        ),
        table: ({ children }) => (
          <div className='overflow-x-auto my-2'>
            <table className='border-collapse border border-muted'>{children}</table>
          </div>
        ),
        td: ({ children }) => (
          <td className='border border-muted p-2'>{children}</td>
        ),
        th: ({ children }) => (
          <th className='border border-muted p-2 bg-muted font-bold'>{children}</th>
        ),
      }}
    >
      {linkifiedContent}
    </ReactMarkdown>
  )
}
