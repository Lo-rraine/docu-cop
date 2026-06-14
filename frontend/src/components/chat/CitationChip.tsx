import { Badge } from '@/components/ui/badge'
import type { CitationPayload } from '@/lib/chat'

export interface CitationChipProps {
  citation: CitationPayload
  selected: boolean
  onSelect: (c: CitationPayload) => void
}

export function CitationChip({ citation, selected, onSelect }: CitationChipProps) {
  const label = `${citation.ticker} ${citation.filing_type} ${citation.filing_year}`

  return (
    <button
      onClick={() => onSelect(citation)}
      className={`transition-colors rounded-full px-3 py-1 text-sm ${
        selected
          ? 'border-foreground bg-foreground/5 text-foreground'
          : 'border-border bg-background text-muted-foreground hover:text-foreground'
      } border`}
    >
      <span className='font-semibold'>
        [{citation.citation_index}]
      </span>
      {' '}
      <span className='truncate max-w-[200px]'>{label}</span>
    </button>
  )
}
