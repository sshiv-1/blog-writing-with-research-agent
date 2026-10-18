import { useState } from 'react'
import {
  Presentation,
  Download,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
  Loader2,
  ChevronDown,
  ChevronUp,
  FileCode,
} from 'lucide-react'
import {
  type SlideJobStatus,
  type StartSlidesRequest,
  downloadSlideArtifact,
} from '@/api/client'
import { useAuth } from '@/context/AuthContext'
import { useModelSettings, PROVIDERS } from '@/context/ModelSettingsContext'

interface SlidesPanelProps {
  jobId: string
  blogIsDone: boolean
  audience?: string
  status: SlideJobStatus | null
  isLoading: boolean
  error: string | null
  pdfBlobUrl: string | null
  isPdfLoading: boolean
  pdfError: string | null
  start: (opts?: StartSlidesRequest, byokHeaders?: Record<string, string>) => Promise<void>
  retryPdf: () => Promise<void>
}

const SLIDE_COUNT_OPTIONS = [
  { value: 8, label: '8 slides', desc: 'Concise summary' },
  { value: 10, label: '10 slides', desc: 'Standard lecture' },
  { value: 12, label: '12 slides', desc: 'In-depth breakdown' },
  { value: 16, label: '16 slides', desc: 'Full presentation' },
]

function getStageDescription(stage: string): string {
  switch (stage) {
    case 'queued':
      return 'Job queued, waiting for runner...'
    case 'planning':
      return 'Planning slide structure and design brief...'
    case 'writing_latex':
    case 'writing_tex':
      return 'Typesetting Beamer LaTeX presentation...'
    case 'compiling':
    case 'compiling_pdf':
      return 'Compiling Beamer PDF and PPTX...'
    case 'done':
      return 'Slides ready'
    default:
      return 'Generating slides...'
  }
}

export default function SlidesPanel({
  jobId,
  blogIsDone,
  audience,
  status,
  isLoading,
  error,
  pdfBlobUrl,
  isPdfLoading,
  pdfError,
  start,
  retryPdf,
}: SlidesPanelProps) {
  const { user } = useAuth()
  const {
    effectiveSlidesProvider,
    effectiveSlidesModel,
    hasKeyForProvider,
    getGuestKey,
    savedKeys,
    setIsSettingsOpen,
  } = useModelSettings()

  const [slideCount, setSlideCount] = useState<number>(10)
  const [warningsOpen, setWarningsOpen] = useState(false)
  const [localKeyError, setLocalKeyError] = useState<string | null>(null)
  const [downloadingFormat, setDownloadingFormat] = useState<'pdf' | 'pptx' | 'tex' | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const isGenerating = isLoading || status?.status === 'queued' || status?.status === 'running'
  const isDone = status?.status === 'done'
  const isError = Boolean(error || status?.status === 'error' || localKeyError)

  // Handle generation start with effective slides model and BYOK headers
  const handleStart = () => {
    if (!blogIsDone || isGenerating) return

    setLocalKeyError(null)

    if (effectiveSlidesProvider !== 'groq' && !hasKeyForProvider(effectiveSlidesProvider)) {
      setLocalKeyError(
        `API key required for ${PROVIDERS[effectiveSlidesProvider]?.name || effectiveSlidesProvider}. Please enter your key in settings.`
      )
      setIsSettingsOpen(true)
      return
    }

    let byokHeaders: Record<string, string> | undefined
    if (effectiveSlidesProvider === 'groq') {
      const guestGroqKey = getGuestKey('groq')
      const savedGroqKey = user && savedKeys.some((k) => k.provider === 'groq')
      if (guestGroqKey || savedGroqKey) {
        byokHeaders = {
          'X-LLM-Slides-Provider': effectiveSlidesProvider,
          'X-LLM-Slides-Model': effectiveSlidesModel,
        }
        if (guestGroqKey) {
          byokHeaders['X-LLM-Key'] = guestGroqKey
        }
      }
    } else {
      byokHeaders = {
        'X-LLM-Slides-Provider': effectiveSlidesProvider,
        'X-LLM-Slides-Model': effectiveSlidesModel,
      }
      const guestKey = getGuestKey(effectiveSlidesProvider)
      if (guestKey) {
        byokHeaders['X-LLM-Key'] = guestKey
      }
    }

    void start(
      {
        slide_count: slideCount,
        audience: audience || undefined,
      },
      byokHeaders
    )
  }

  // Handle authenticated download
  const handleDownload = async (format: 'pdf' | 'pptx' | 'tex') => {
    setDownloadError(null)
    setDownloadingFormat(format)
    try {
      await downloadSlideArtifact(jobId, format, 'slides')
    } catch (err: any) {
      setDownloadError(err.message || `Failed to download ${format.toUpperCase()}`)
    } finally {
      setDownloadingFormat(null)
    }
  }

  // ── ERROR STATE ──────────────────────────────────────────────────────────
  if (isError) {
    return (
      <div
        className="p-8 text-center flex flex-col items-center justify-center"
        style={{
          borderRadius: '6px',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div
          className="w-12 h-12 flex items-center justify-center mb-4"
          style={{
            borderRadius: '6px',
            background: 'var(--color-error-bg)',
            border: '1px solid rgba(192,57,43,0.2)',
          }}
        >
          <AlertCircle className="h-6 w-6" style={{ color: 'var(--color-error)' }} strokeWidth={1.5} />
        </div>
        <h3
          className="text-base font-semibold mb-2"
          style={{ color: 'var(--color-ink)', letterSpacing: '-0.02em' }}
        >
          Slide generation failed
        </h3>
        <p className="text-sm max-w-[42ch] mb-6" style={{ color: 'var(--color-ink-3)' }}>
          {error || status?.error || 'An unexpected error occurred while generating slides.'}
        </p>
        <button
          type="button"
          onClick={handleStart}
          className="flex items-center gap-2 h-9 px-4 text-sm font-medium transition-colors cursor-pointer"
          style={{
            borderRadius: '4px',
            background: 'var(--color-ink)',
            color: 'var(--color-ink-inv)',
          }}
        >
          <RefreshCw className="h-4 w-4" strokeWidth={2} />
          Try again
        </button>
      </div>
    )
  }

  // ── IN-PROGRESS / GENERATING STATE ──────────────────────────────────────
  if (isGenerating) {
    const progress = status?.progress ?? 5
    const stage = status?.stage ?? 'queued'

    return (
      <div
        className="p-8 sm:p-12 text-center flex flex-col items-center justify-center"
        style={{
          borderRadius: '6px',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div
          className="w-12 h-12 flex items-center justify-center mb-5"
          style={{
            borderRadius: '6px',
            background: 'var(--color-accent-muted)',
            border: '1px solid var(--color-accent-ring)',
          }}
        >
          <Presentation className="h-6 w-6" style={{ color: 'var(--color-accent)' }} strokeWidth={1.75} />
        </div>

        <h3
          className="text-lg font-bold mb-1.5"
          style={{ color: 'var(--color-ink)', letterSpacing: '-0.02em' }}
        >
          Generating presentation slides
        </h3>

        <p className="text-sm mb-6 flex items-center gap-2" style={{ color: 'var(--color-ink-3)' }}>
          <Loader2 className="h-4 w-4 animate-spin inline" style={{ color: 'var(--color-accent)' }} />
          <span>{getStageDescription(stage)}</span>
        </p>

        {/* Progress bar */}
        <div className="w-full max-w-md mb-4">
          <div
            className="w-full h-2 overflow-hidden"
            style={{
              borderRadius: '9999px',
              background: 'var(--color-border)',
            }}
          >
            <div
              className="h-full transition-all duration-500 ease-out"
              style={{
                width: `${Math.max(progress, 8)}%`,
                background: 'var(--color-accent)',
                borderRadius: '9999px',
              }}
            />
          </div>
          <div className="flex justify-between items-center text-xs mt-2" style={{ color: 'var(--color-ink-4)' }}>
            <span>Stage: {stage}</span>
            <span>{progress}%</span>
          </div>
        </div>

        <p className="text-xs max-w-sm mt-3" style={{ color: 'var(--color-ink-4)' }}>
          Includes Beamer LaTeX compilation with Tectonic and editable PowerPoint PPTX generation with speaker notes.
        </p>
      </div>
    )
  }

  // ── DONE STATE (SLIDES READY) ───────────────────────────────────────────
  if (isDone) {
    const slideCountRendered = status?.slide_count ?? slideCount
    const warnings = status?.warnings ?? []

    return (
      <div className="space-y-0">
        {/* Toolbar */}
        <div
          className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5"
          style={{
            borderRadius: '6px 6px 0 0',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderBottom: '1px solid var(--color-border-soft)',
          }}
        >
          {/* Left: Info badge */}
          <div className="flex items-center gap-2.5">
            <div className="flex items-center gap-1.5 text-xs font-medium" style={{ color: 'var(--color-ink-2)' }}>
              <Presentation className="h-4 w-4" style={{ color: 'var(--color-accent)' }} strokeWidth={1.75} />
              <span>{slideCountRendered} slides</span>
            </div>

            <span
              className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5"
              style={{
                borderRadius: '4px',
                background: 'var(--color-success-bg)',
                color: 'var(--color-success)',
                border: '1px solid rgba(45,122,79,0.2)',
              }}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: 'var(--color-success)' }}
                aria-hidden
              />
              Ready
            </span>
          </div>

          {/* Right: Download buttons */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => handleDownload('pdf')}
              disabled={downloadingFormat === 'pdf'}
              className="flex items-center gap-1.5 h-7 px-2.5 text-xs font-medium rounded transition-colors disabled:opacity-50 cursor-pointer"
              style={{
                borderRadius: '4px',
                background: 'var(--color-elevated)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-ink-2)',
              }}
            >
              <Download className={`h-3.5 w-3.5 ${downloadingFormat === 'pdf' ? 'animate-bounce' : ''}`} />
              PDF
            </button>

            <button
              type="button"
              onClick={() => handleDownload('pptx')}
              disabled={downloadingFormat === 'pptx'}
              className="flex items-center gap-1.5 h-7 px-2.5 text-xs font-medium rounded transition-colors disabled:opacity-50 cursor-pointer"
              style={{
                borderRadius: '4px',
                background: 'var(--color-elevated)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-ink-2)',
              }}
            >
              <Download className={`h-3.5 w-3.5 ${downloadingFormat === 'pptx' ? 'animate-bounce' : ''}`} />
              PPTX
            </button>

            <button
              type="button"
              onClick={() => handleDownload('tex')}
              disabled={downloadingFormat === 'tex'}
              className="flex items-center gap-1.5 h-7 px-2.5 text-xs font-medium rounded transition-colors disabled:opacity-50 cursor-pointer"
              style={{
                borderRadius: '4px',
                background: 'var(--color-elevated)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-ink-4)',
              }}
              title="Download raw LaTeX source"
            >
              <FileCode className={`h-3.5 w-3.5 ${downloadingFormat === 'tex' ? 'animate-bounce' : ''}`} />
              .tex
            </button>
          </div>
        </div>

        {/* Download failure error notice */}
        {downloadError && (
          <div className="px-4 py-2 bg-[var(--color-error-bg)] text-[var(--color-error)] text-xs border-x border-[var(--color-border)] flex items-center justify-between">
            <span>{downloadError}</span>
            <button
              type="button"
              onClick={() => setDownloadError(null)}
              className="underline ml-2 text-xs hover:opacity-80 focus:outline-none"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Warnings dropdown (if compiler emitted warnings) */}
        {warnings.length > 0 && (
          <div
            style={{
              background: 'var(--color-surface)',
              borderLeft: '1px solid var(--color-border)',
              borderRight: '1px solid var(--color-border)',
              borderBottom: '1px solid var(--color-border-soft)',
            }}
          >
            <button
              type="button"
              onClick={() => setWarningsOpen(!warningsOpen)}
              className="w-full flex items-center justify-between px-4 py-2 text-xs font-medium cursor-pointer transition-colors"
              style={{ color: 'var(--color-ink-3)', background: 'transparent', border: 'none' }}
            >
              <span className="flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5" style={{ color: 'var(--color-accent)' }} />
                <span>Compiler notes ({warnings.length})</span>
              </span>
              {warningsOpen ? (
                <ChevronUp className="h-3.5 w-3.5" style={{ color: 'var(--color-ink-4)' }} />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" style={{ color: 'var(--color-ink-4)' }} />
              )}
            </button>
            {warningsOpen && (
              <div
                className="px-4 py-2.5 space-y-1 font-mono text-[11px] max-h-36 overflow-y-auto"
                style={{
                  background: 'var(--color-canvas)',
                  borderTop: '1px solid var(--color-border-soft)',
                  color: 'var(--color-ink-3)',
                }}
              >
                {warnings.map((w, idx) => (
                  <div key={idx} className="leading-relaxed">
                    • {w}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* PDF Preview Frame */}
        <div
          className="relative w-full overflow-hidden"
          style={{
            borderRadius: '0 0 6px 6px',
            border: '1px solid var(--color-border)',
            borderTop: 'none',
            background: 'var(--color-canvas)',
            height: '72vh',
            minHeight: '520px',
            maxHeight: '860px',
          }}
        >
          {isPdfLoading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: 'var(--color-accent)' }} />
              <p className="text-sm font-medium" style={{ color: 'var(--color-ink-3)' }}>
                Loading slide preview…
              </p>
            </div>
          )}

          {pdfError && !isPdfLoading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center">
              <div
                className="w-10 h-10 flex items-center justify-center mb-3"
                style={{
                  borderRadius: '6px',
                  background: 'var(--color-error-bg)',
                  border: '1px solid rgba(192,57,43,0.2)',
                }}
              >
                <AlertCircle className="h-5 w-5" style={{ color: 'var(--color-error)' }} />
              </div>
              <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-ink)' }}>
                Unable to load PDF preview in browser
              </p>
              <p className="text-xs max-w-sm mb-4" style={{ color: 'var(--color-ink-4)' }}>
                {pdfError}. You can still download the files directly using the buttons above.
              </p>
              <button
                type="button"
                onClick={() => void retryPdf()}
                className="flex items-center gap-1.5 h-8 px-3 text-xs font-medium cursor-pointer"
                style={{
                  borderRadius: '4px',
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-ink-2)',
                }}
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Retry preview
              </button>
            </div>
          )}

          {pdfBlobUrl && !isPdfLoading && !pdfError && (
            <iframe
              src={pdfBlobUrl}
              className="w-full h-full border-0"
              title="Slide Deck Preview"
            />
          )}
        </div>
      </div>
    )
  }

  // ── EMPTY STATE (NOT GENERATED YET) ─────────────────────────────────────
  return (
    <div
      className="p-8 sm:p-12"
      style={{
        borderRadius: '6px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
      }}
    >
      <div className="max-w-xl mx-auto text-center">
        <div
          className="w-12 h-12 mx-auto flex items-center justify-center mb-5"
          style={{
            borderRadius: '6px',
            background: 'var(--color-elevated)',
            border: '1px solid var(--color-border)',
          }}
        >
          <Presentation className="h-6 w-6" style={{ color: 'var(--color-accent)' }} strokeWidth={1.75} />
        </div>

        <h3
          className="text-xl font-bold mb-2.5"
          style={{ color: 'var(--color-ink)', letterSpacing: '-0.025em' }}
        >
          Generate Presentation Slides
        </h3>

        <p className="text-sm leading-relaxed mb-8" style={{ color: 'var(--color-ink-3)' }}>
          Transform this technical article into an executive slide deck. Includes compiled Beamer LaTeX PDF typography with professional design rhythm, plus an editable PowerPoint (.pptx) file with speaker notes.
        </p>

        {/* Slide Count Option Selector */}
        <div className="mb-8 text-left">
          <label
            className="block text-xs font-semibold uppercase tracking-wider mb-3"
            style={{ color: 'var(--color-ink-3)', letterSpacing: '0.05em' }}
          >
            Slide Count
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {SLIDE_COUNT_OPTIONS.map(opt => {
              const isSelected = slideCount === opt.value
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setSlideCount(opt.value)}
                  className="p-3 text-left transition-all cursor-pointer"
                  style={{
                    borderRadius: '4px',
                    background: isSelected ? 'var(--color-elevated)' : 'var(--color-canvas)',
                    border: isSelected
                      ? '1px solid var(--color-accent)'
                      : '1px solid var(--color-border)',
                    boxShadow: isSelected ? '0 1px 3px rgba(181, 129, 58, 0.15)' : 'none',
                  }}
                >
                  <p
                    className="text-sm font-semibold mb-0.5"
                    style={{
                      color: isSelected ? 'var(--color-accent)' : 'var(--color-ink)',
                    }}
                  >
                    {opt.label}
                  </p>
                  <p className="text-[11px]" style={{ color: 'var(--color-ink-4)' }}>
                    {opt.desc}
                  </p>
                </button>
              )
            })}
          </div>
        </div>

        {/* Primary CTA */}
        <div className="flex flex-col items-center gap-3">
          <button
            type="button"
            disabled={!blogIsDone}
            onClick={handleStart}
            className="flex items-center justify-center gap-2 h-11 px-6 text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            style={{
              borderRadius: '4px',
              background: 'var(--color-ink)',
              color: 'var(--color-ink-inv)',
              border: 'none',
            }}
          >
            <Presentation className="h-4 w-4" />
            Generate Slides ({slideCount} slides)
          </button>

          {!blogIsDone && (
            <p className="text-xs" style={{ color: 'var(--color-ink-4)' }}>
              Wait for article generation to complete before creating slides.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
