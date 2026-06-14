import { useEffect, useState } from 'react'

interface Stage {
  id: string
  label: string
  completed: boolean
  active: boolean
}

interface ProcessingProgressProps {
  status: string | null
}

export function ProcessingProgress({ status }: ProcessingProgressProps) {
  const [stages, setStages] = useState<Stage[]>([
    { id: 'search', label: 'Searching SEC filings', completed: false, active: true },
    { id: 'read', label: 'Reading relevant sections', completed: false, active: false },
    { id: 'verify', label: 'Verifying evidence', completed: false, active: false },
    { id: 'generate', label: 'Generating answer', completed: false, active: false },
  ])

  // Parse status messages to update stage progress
  useEffect(() => {
    if (!status) return

    const statusLower = status.toLowerCase()

    setStages((prev) => {
      const updated = [...prev]

      // Mark stages as completed based on status keywords
      if (statusLower.includes('search') && !statusLower.includes('reading')) {
        updated[0] = { ...updated[0], completed: true, active: false }
        updated[1] = { ...updated[1], active: true }
      } else if (statusLower.includes('read') && !statusLower.includes('verif')) {
        updated[0] = { ...updated[0], completed: true }
        updated[1] = { ...updated[1], completed: true, active: false }
        updated[2] = { ...updated[2], active: true }
      } else if (statusLower.includes('verif') && !statusLower.includes('generat')) {
        updated[0] = { ...updated[0], completed: true }
        updated[1] = { ...updated[1], completed: true }
        updated[2] = { ...updated[2], completed: true, active: false }
        updated[3] = { ...updated[3], active: true }
      } else if (statusLower.includes('generat')) {
        updated[0] = { ...updated[0], completed: true }
        updated[1] = { ...updated[1], completed: true }
        updated[2] = { ...updated[2], completed: true }
        updated[3] = { ...updated[3], active: true }
      }

      return updated
    })
  }, [status])

  return (
    <div className='space-y-3 py-4'>
      {stages.map((stage) => (
        <div key={stage.id} className='flex items-center gap-3'>
          <div className='flex-shrink-0 w-5 h-5 flex items-center justify-center'>
            {stage.completed ? (
              <div className='w-5 h-5 rounded-full bg-green-500/20 border border-green-500 flex items-center justify-center'>
                <svg className='w-3 h-3 text-green-600' fill='currentColor' viewBox='0 0 20 20'>
                  <path
                    fillRule='evenodd'
                    d='M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z'
                    clipRule='evenodd'
                  />
                </svg>
              </div>
            ) : stage.active ? (
              <div className='w-5 h-5 rounded-full border-2 border-primary border-transparent border-t-primary animate-spin' />
            ) : (
              <div className='w-5 h-5 rounded-full border-2 border-muted-foreground/30' />
            )}
          </div>
          <span
            className={`text-sm font-medium transition-colors ${
              stage.completed
                ? 'text-foreground/60'
                : stage.active
                  ? 'text-foreground'
                  : 'text-foreground/40'
            }`}
          >
            {stage.label}
          </span>
        </div>
      ))}
    </div>
  )
}
