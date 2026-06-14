interface PipelineStatusProps {
  status: string | null
}

export function PipelineStatus({ status }: PipelineStatusProps) {
  const message = status ?? 'Researching filings…'

  return (
    <div
      className='py-4 px-0 text-sm font-medium'
      aria-live='polite'
      style={{
        background: 'linear-gradient(90deg, hsl(var(--muted-foreground)), hsl(var(--foreground)), hsl(var(--muted-foreground)))',
        backgroundSize: '200% 100%',
        animation: 'shimmer 2.5s infinite',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        backgroundClip: 'text',
      }}
    >
      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
      {message}
    </div>
  )
}
