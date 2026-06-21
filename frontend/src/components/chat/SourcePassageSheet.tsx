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

    const loadContext = async () => {
      try {
        const data = await getChunkContext(citation.chunk_id)
        setContext(data)
        setError(null)
      } catch (err) {
        console.error('Error loading chunk context:', err)
        setError(err instanceof Error ? err.message : 'Failed to load passage context')
        setContext(null)
      } finally {
        setLoading(false)
      }
    }

    loadContext()
  }, [citation])

  const open = citation !== null

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setContext(null)
      setError(null)
      setLoading(false)
      onClose()
    }
  }

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent className='flex flex-col h-full p-0'>
        {loading && (
          <div className='flex items-center justify-center h-full'>
            <div className='animate-spin rounded-full h-8 w-8 border-b-2 border-foreground' />
          </div>
        )}

        {error && (
          <>
            <SheetHeader>
              <SheetTitle className='flex items-center gap-2'>
                <Badge variant='outline'>[{citation?.citation_index}]</Badge>
                <span>
                  {citation?.ticker} {citation?.filing_type} {citation?.filing_year}
                </span>
              </SheetTitle>
            </SheetHeader>
            <div className='flex-1 overflow-y-auto px-6 pb-6'>
              <div className='rounded-lg border border-destructive/20 bg-destructive/5 p-4'>
                <p className='text-sm text-destructive font-medium mb-2'>⚠️ Error loading full context</p>
                <p className='text-sm text-destructive/80 mb-3'>{error}</p>
                <p className='text-xs text-foreground/60'>Excerpt from citation:</p>
                <p className='text-sm text-muted-foreground mt-2 rounded p-2 bg-muted/30'>{citation?.excerpt}</p>
              </div>
            </div>
          </>
        )}

        {context && (
          <>
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

            <div className='flex-1 overflow-y-auto px-6'>
              <div className='space-y-6 pb-6'>
                {context.prev && (
                  <div className='space-y-2'>
                    <p className='text-xs font-semibold text-foreground/60 uppercase tracking-wider'>Previous Context</p>
                    <div className='rounded-lg border border-border/50 p-4 bg-muted/30'>
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
                  <p className='text-xs font-semibold text-foreground/60 uppercase tracking-wider'>Cited Passage</p>
                  <div className='rounded-lg border border-primary/40 bg-primary/8 p-4 shadow-sm overflow-x-auto'>
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
                    <p className='text-xs font-semibold text-foreground/60 uppercase tracking-wider'>Next Context</p>
                    <div className='rounded-lg border border-border/50 p-4 bg-muted/30'>
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
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
