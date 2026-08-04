import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import { Progress } from '@/components/ui/progress'
import type { JobStatus } from '@/api/client'

const STAGES = [
  { key: 'queued',      label: 'Queued',              desc: 'Waiting to start…' },
  { key: 'routing',     label: 'Analysing Topic',     desc: 'Deciding research strategy…' },
  { key: 'researching', label: 'Researching Sources', desc: 'Searching the web for evidence…' },
  { key: 'planning',    label: 'Building Outline',    desc: 'Structuring sections and goals…' },
  { key: 'writing',     label: 'Drafting Sections',   desc: 'Writing all sections in parallel…' },
  { key: 'finalizing',  label: 'Polishing Article',   desc: 'Assembling the final post…' },
  { key: 'done',        label: 'Complete',            desc: 'Your blog is ready!' },
]

interface Props {
  jobStatus: JobStatus | null
}

export default function ProgressStepper({ jobStatus }: Props) {
  const currentStage = jobStatus?.stage ?? 'queued'
  const progress = jobStatus?.progress ?? 0

  const currentIndex = STAGES.findIndex(s => s.key === currentStage)

  return (
    <div className="w-full space-y-8">
      {/* Progress bar */}
      <div className="space-y-3">
        <div className="flex justify-between items-center text-sm">
          <span className="text-slate-400">Progress</span>
          <span className="text-purple-400 font-semibold tabular-nums">{progress}%</span>
        </div>
        <div className="relative">
          <Progress
            value={progress}
            className="h-2 bg-white/10"
          />
          {/* Glow overlay on progress */}
          <div
            className="absolute top-0 left-0 h-2 rounded-full transition-all duration-700 ease-out pointer-events-none"
            style={{
              width: `${progress}%`,
              background: 'linear-gradient(90deg, #7c3aed, #06b6d4)',
              boxShadow: '0 0 12px rgba(124, 58, 237, 0.6)',
            }}
          />
        </div>
      </div>

      {/* Stage steps */}
      <div className="space-y-3">
        {STAGES.map((stage, idx) => {
          const isDone = idx < currentIndex || currentStage === 'done'
          const isCurrent = stage.key === currentStage && currentStage !== 'done'

          return (
            <div
              key={stage.key}
              className={`flex items-center gap-4 p-3 rounded-xl transition-all duration-300 ${
                isCurrent
                  ? 'bg-purple-500/10 border border-purple-500/30'
                  : isDone
                  ? 'bg-white/[0.02]'
                  : 'opacity-40'
              }`}
            >
              {/* Icon */}
              <div className="flex-shrink-0 w-7 h-7 flex items-center justify-center">
                {isDone ? (
                  <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                ) : isCurrent ? (
                  <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
                ) : (
                  <Circle className="w-6 h-6 text-slate-600" />
                )}
              </div>

              {/* Text */}
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${
                  isDone ? 'text-slate-400 line-through decoration-slate-600' :
                  isCurrent ? 'text-white' : 'text-slate-500'
                }`}>
                  {stage.label}
                </p>
                {isCurrent && (
                  <p className="text-xs text-purple-300/70 mt-0.5 animate-pulse">
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
