import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import type { JobStatus } from '@/api/client'

const STAGES = [
  { key: 'queued',      label: 'Queued',              desc: 'Waiting to start…' },
  { key: 'routing',     label: 'Analysing topic',     desc: 'Deciding research strategy…' },
  { key: 'researching', label: 'Researching sources', desc: 'Searching the web for evidence…' },
  { key: 'planning',    label: 'Building outline',    desc: 'Structuring sections and goals…' },
  { key: 'writing',     label: 'Drafting sections',   desc: 'Writing all sections in parallel…' },
  { key: 'finalizing',  label: 'Polishing article',   desc: 'Assembling the final post…' },
  { key: 'done',        label: 'Complete',            desc: 'Your article is ready.' },
]

interface Props {
  jobStatus: JobStatus | null
}

export default function ProgressStepper({ jobStatus }: Props) {
  const currentStage = jobStatus?.stage ?? 'queued'
  const progress = jobStatus?.progress ?? 0

  const currentIndex = STAGES.findIndex(s => s.key === currentStage)

  return (
    <div className="w-full space-y-6">
      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between items-center text-xs" style={{ color: 'var(--color-ink-4)' }}>
          <span>Progress</span>
          <span
            className="font-semibold tabular-nums"
            style={{ color: 'var(--color-accent)', fontVariantNumeric: 'tabular-nums' }}
          >
            {progress}%
          </span>
        </div>
        {/* Track */}
        <div
          className="relative h-1 overflow-hidden"
          style={{ background: 'var(--color-border)', borderRadius: '1px' }}
        >
          <div
            className="absolute inset-y-0 left-0 transition-all duration-700"
            style={{
              width: `${progress}%`,
              background: 'var(--color-accent)',
              borderRadius: '1px',
              transitionTimingFunction: 'var(--ease-out-expo)',
            }}
          />
        </div>
      </div>

      {/* Stage steps */}
      <div className="space-y-0.5">
        {STAGES.map((stage, idx) => {
          const isDone = idx < currentIndex || currentStage === 'done'
          const isCurrent = stage.key === currentStage && currentStage !== 'done'

          return (
            <div
              key={stage.key}
              className="flex items-center gap-3 px-3 py-2.5 transition-colors"
              style={{
                borderRadius: '4px',
                background: isCurrent ? 'var(--color-accent-muted)' : 'transparent',
                opacity: !isDone && !isCurrent ? 0.38 : 1,
              }}
            >
              {/* Icon */}
              <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
                {isDone ? (
                  <CheckCircle2
                    className="w-4.5 h-4.5"
                    style={{ color: 'var(--color-success)' }}
                    strokeWidth={2}
                  />
                ) : isCurrent ? (
                  <Loader2
                    className="w-4.5 h-4.5 animate-spin"
                    style={{ color: 'var(--color-accent)' }}
                    strokeWidth={2}
                  />
                ) : (
                  <Circle
                    className="w-4.5 h-4.5"
                    style={{ color: 'var(--color-border-strong)' }}
                    strokeWidth={1.5}
                  />
                )}
              </div>

              {/* Text */}
              <div className="flex-1 min-w-0">
                <p
                  className="text-sm font-medium"
                  style={{
                    color: isDone
                      ? 'var(--color-ink-4)'
                      : isCurrent
                      ? 'var(--color-ink)'
                      : 'var(--color-ink-4)',
                    textDecoration: isDone ? 'line-through' : 'none',
                  }}
                >
                  {stage.label}
                </p>
                {isCurrent && (
                  <p
                    className="text-xs mt-0.5"
                    style={{ color: 'var(--color-accent)' }}
                  >
                    {stage.desc}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
