export interface CitationMarkerProps {
  index: number
  selected: boolean
  onSelect: () => void
}

export function CitationMarker({ index, selected, onSelect }: CitationMarkerProps) {
  return (
    <button
      onClick={onSelect}
      className={`inline-flex h-5 w-5 items-center justify-center rounded text-xs font-semibold transition-all duration-150 -translate-y-0.5 cursor-pointer ${
        selected
          ? 'bg-primary text-primary-foreground shadow-sm'
          : 'bg-muted/50 text-foreground/70 hover:bg-primary/20 hover:text-primary'
      }`}
      aria-label={`Show source ${index}`}
    >
      {index}
    </button>
  )
}
