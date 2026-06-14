export interface CitationMarkerProps {
  index: number
  selected: boolean
  onSelect: () => void
}

export function CitationMarker({ index, selected, onSelect }: CitationMarkerProps) {
  return (
    <button
      onClick={onSelect}
      className={`inline-flex h-5 w-5 items-center justify-center rounded text-xs font-semibold transition-colors -translate-y-0.5 ${
        selected
          ? 'bg-foreground text-background'
          : 'text-muted-foreground hover:text-foreground'
      }`}
      aria-label={`Show source ${index}`}
    >
      {index}
    </button>
  )
}
