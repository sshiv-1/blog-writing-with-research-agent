import { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeft, AlertCircle, RefreshCw, BookOpen, AlignLeft, Presentation } from 'lucide-react'
import { useJobStatus } from '@/hooks/useJobStatus'
import { useSlideJob } from '@/hooks/useSlideJob'
import ProgressStepper from '@/components/ProgressStepper'
import OutputEditor from '@/components/OutputEditor'
import SourceList from '@/components/SourceList'
import SlidesPanel from '@/components/SlidesPanel'

type ResultTab = 'article' | 'sources' | 'slides'

export default function Result() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const audience = (location.state as { audience?: string } | undefined)?.audience

  const { status, result, isLoading, error } = useJobStatus(jobId ?? null)
  const isDone = status?.status === 'done' && result !== null

  const slideJob = useSlideJob(jobId ?? null)
  const [activeTab, setActiveTab] = useState<ResultTab>('article')

  return (
    <div
      className="min-h-[100dvh] flex flex-col"
      style={{ background: 'var(--color-canvas)' }}
    >
      {/* Top bar */}
      <header
        className="sticky top-0 z-40 flex items-center px-6 h-14"
        style={{
          background: 'var(--color-overlay)',
          borderBottom: '1px solid var(--color-border)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
        }}
      >
        <div className="w-full max-w-6xl mx-auto flex items-center justify-between">
          {/* Left: back + wordmark */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="flex items-center gap-1.5 h-8 px-3 text-sm font-medium transition-colors"
              style={{
                borderRadius: '4px',
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-ink-3)',
              }}
            >
              <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2} />
              New article
            </button>

            <span
              className="text-sm font-semibold tracking-tight hidden sm:block"
              style={{ color: 'var(--color-ink)', letterSpacing: '-0.02em' }}
            >
              SAGE
            </span>
          </div>

          {/* Right: status badge */}
          {isDone && (
            <span
              className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1"
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
              Article ready
            </span>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 w-full">

        {/* ── PROGRESS VIEW ── */}
        {isLoading && !isDone && (
          <div className="flex flex-col items-center justify-center min-h-[calc(100dvh-3.5rem)] px-4 py-12">
            <div className="w-full max-w-sm">
              {/* Heading */}
              <div className="mb-8 text-center">
                <h1
                  className="text-xl font-bold mb-2"
                  style={{ color: 'var(--color-ink)', letterSpacing: '-0.025em' }}
                >
                  Generating your article
                </h1>
                <p className="text-sm" style={{ color: 'var(--color-ink-3)' }}>
                  This takes 30–90 seconds. The agent researches and writes in parallel.
                </p>
              </div>

              {/* Progress card */}
              <div
                className="p-6"
                style={{
                  borderRadius: '6px',
                  background: 'var(--color-elevated)',
                  border: '1px solid var(--color-border)',
                  boxShadow: '0 1px 3px rgba(26,25,22,0.06), 0 8px 24px rgba(26,25,22,0.04)',
                }}
              >
                <ProgressStepper jobStatus={status} />
              </div>
            </div>
          </div>
        )}

        {/* ── ERROR VIEW ── */}
        {error && (
          <div className="flex flex-col items-center justify-center min-h-[calc(100dvh-3.5rem)] px-4 py-12 text-center">
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
            <h2
              className="text-lg font-bold mb-2"
              style={{ color: 'var(--color-ink)', letterSpacing: '-0.02em' }}
            >
              Generation failed
            </h2>
            <p className="text-sm max-w-[36ch] mb-6" style={{ color: 'var(--color-ink-3)' }}>
              {error}
            </p>
            <button
              type="button"
              onClick={() => navigate('/')}
              className="flex items-center gap-2 h-9 px-4 text-sm font-medium transition-colors"
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
        )}

        {/* ── RESULT VIEW ── */}
        {isDone && result && (
          <div className="max-w-6xl mx-auto px-6 py-10 sm:py-12">

            {/* Article header */}
            <div className="mb-8">
              <p
                className="text-xs font-semibold uppercase mb-3"
                style={{ color: 'var(--color-accent)', letterSpacing: '0.1em' }}
              >
                Generated Article
              </p>
              <h1
                className="text-2xl sm:text-3xl font-bold leading-tight mb-0"
                style={{ color: 'var(--color-ink)', letterSpacing: '-0.03em' }}
              >
                {result.title}
              </h1>

              {/* Metadata strip */}
              <div
                className="flex flex-wrap items-center gap-4 mt-4 pt-4"
                style={{ borderTop: '1px solid var(--color-border)' }}
              >
                <span className="text-xs" style={{ color: 'var(--color-ink-4)' }}>
                  ~{result.draft.split(/\s+/).filter(Boolean).length.toLocaleString()} words
                </span>
                <span className="text-xs" style={{ color: 'var(--color-ink-4)' }}>
                  {result.outline.length} sections
                </span>
                <span className="text-xs" style={{ color: 'var(--color-ink-4)' }}>
                  {result.sources.length} sources cited
                </span>
              </div>
            </div>

            {/* Tab navigation */}
            <div
              className="flex items-center gap-0 mb-6"
              style={{ borderBottom: '1px solid var(--color-border)' }}
            >
              {([
                { id: 'article' as ResultTab, icon: AlignLeft, label: 'Article' },
                { id: 'sources' as ResultTab, icon: BookOpen, label: `Sources (${result.sources.length})` },
                { id: 'slides' as ResultTab, icon: Presentation, label: 'Slides' },
              ] as const).map(({ id, icon: Icon, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setActiveTab(id)}
                  className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium relative transition-colors"
                  style={{
                    color: activeTab === id ? 'var(--color-ink)' : 'var(--color-ink-4)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    borderBottom: activeTab === id
                      ? '2px solid var(--color-accent)'
                      : '2px solid transparent',
                    marginBottom: '-1px',
                  }}
                >
                  <Icon className="h-4 w-4" strokeWidth={1.75} />
                  {label}
                  {id === 'slides' && slideJob.status?.status === 'done' && (
                    <span
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ background: 'var(--color-success)' }}
                      aria-hidden
                    />
                  )}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div style={{ display: activeTab === 'article' ? 'block' : 'none' }}>
              <OutputEditor result={result} />
            </div>

            <div style={{ display: activeTab === 'sources' ? 'block' : 'none' }} className="max-w-2xl">
              <SourceList sources={result.sources} />
            </div>

            <div style={{ display: activeTab === 'slides' ? 'block' : 'none' }}>
              <SlidesPanel
                jobId={jobId ?? ''}
                blogIsDone={isDone}
                audience={audience}
                status={slideJob.status}
                isLoading={slideJob.isLoading}
                error={slideJob.error}
                pdfBlobUrl={slideJob.pdfBlobUrl}
                isPdfLoading={slideJob.isPdfLoading}
                pdfError={slideJob.pdfError}
                start={slideJob.start}
                retryPdf={slideJob.retryPdf}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
