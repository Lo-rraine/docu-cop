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
      className={`transition-all duration-150 rounded-full px-3 py-1.5 text-xs font-medium border cursor-pointer ${
        selected
          ? 'border-primary bg-primary/15 text-primary shadow-sm'
          : 'border-border/60 bg-muted/40 text-foreground/70 hover:bg-muted/70 hover:text-foreground'
      }`}
    >
      <span className='font-semibold'>
        [{citation.citation_index}]
      </span>
      {' '}
      <span className='truncate max-w-[200px]'>{label}</span>
    </button>
  )
}
