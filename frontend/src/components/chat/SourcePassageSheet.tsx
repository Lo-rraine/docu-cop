import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import type { CitationPayload } from '@/lib/chat'
import type { ChunkContext } from '@/lib/documents'
import { getChunkContext } from '@/lib/documents'
import { AssistantMarkdown } from './AssistantMarkdown'

interface SourcePassageSheetProps {
  citation: CitationPayload | null
  onClose: () => void
}

export function SourcePassageSheet({ citation, onClose }: SourcePassageSheetProps) {
  const [context, setContext] = useState<ChunkContext | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!citation) {
      setContext(null)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)

    getChunkContext(citation.chunk_id)
      .then((data) => {
        setContext(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err?.message || 'Failed to load passage context')
        setLoading(false)
      })
  }, [citation])

  const open = citation !== null

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent className='sm:max-w-2xl'>
        {loading ? (
          <div className='flex items-center justify-center h-full'>
            <div className='animate-spin rounded-full h-8 w-8 border-b-2 border-foreground' />
          </div>
        ) : error ? (
          <div className='space-y-4'>
            <p className='text-sm text-destructive'>{error}</p>
            {citation && (
              <div className='space-y-2'>
                <p className='text-sm font-medium'>Excerpt:</p>
                <p className='text-sm text-muted-foreground'>{citation.excerpt}</p>
              </div>
            )}
          </div>
        ) : context ? (
          <div className='space-y-6'>
            <SheetHeader>
              <SheetTitle className='flex items-center gap-2'>
                <Badge variant='outline'>[{citation!.citation_index}]</Badge>
                <span>
                  {context.chunk.ticker} {context.chunk.filing_type} {context.chunk.filing_year}
                </span>
              </SheetTitle>
              {context.chunk.heading && (
                <p className='text-sm text-muted-foreground'>{context.chunk.heading}</p>
              )}
            </SheetHeader>

            {context.prev && (
              <div className='space-y-2'>
                <p className='text-xs font-semibold text-muted-foreground uppercase'>Previous Context</p>
                <div className='rounded-lg border border-muted p-3 bg-muted/50'>
                  <AssistantMarkdown
                    content={context.prev.text}
                    citations={[]}
                    selectedIndex={null}
                    onSelect={() => {}}
                  />
                </div>
              </div>
            )}

            <div className='space-y-2'>
              <p className='text-xs font-semibold text-muted-foreground uppercase'>Cited Passage</p>
              <div className='rounded-lg border border-primary/50 bg-primary/5 p-3'>
                <AssistantMarkdown
                  content={context.chunk.text}
                  citations={[]}
                  selectedIndex={null}
                  onSelect={() => {}}
                />
              </div>
            </div>

            {context.next && (
              <div className='space-y-2'>
                <p className='text-xs font-semibold text-muted-foreground uppercase'>Next Context</p>
                <div className='rounded-lg border border-muted p-3 bg-muted/50'>
                  <AssistantMarkdown
                    content={context.next.text}
                    citations={[]}
                    selectedIndex={null}
                    onSelect={() => {}}
                  />
                </div>
              </div>
            )}
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
