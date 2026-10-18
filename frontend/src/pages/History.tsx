import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText,
  Presentation,
  Trash2,
  ExternalLink,
  Clock,
  AlertCircle,
  Plus,
  RefreshCw,
  CheckCircle2,
  Loader2,
} from 'lucide-react'
import Header from '@/components/Header'
import { useAuth } from '@/context/AuthContext'
import { useModelSettings } from '@/context/ModelSettingsContext'
import { getUserJobs, deleteUserJob, type UserJobItem } from '@/api/client'

export default function History() {
  const navigate = useNavigate()
  const { user, isConfigured } = useAuth()
  const { setIsSignInOpen } = useModelSettings()

  const [jobs, setJobs] = useState<UserJobItem[]>([])
  const [total, setTotal] = useState<number>(0)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [pageOffset, setPageOffset] = useState<number>(0)
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false)
  const PAGE_SIZE = 15

  const fetchJobs = useCallback(async (offset: number, append: boolean = false) => {
    if (!user) {
      setIsLoading(false)
      return
    }

    if (append) {
      setIsLoadingMore(true)
    } else {
      setIsLoading(true)
    }
    setError(null)

    try {
      const data = await getUserJobs(PAGE_SIZE, offset)
      if (append) {
        setJobs((prev) => [...prev, ...data.items])
      } else {
        setJobs(data.items)
      }
      setTotal(data.total)
      setPageOffset(offset)
    } catch (err: any) {
      setError(err.message || 'Failed to load article history.')
    } finally {
      setIsLoading(false)
      setIsLoadingMore(false)
    }
  }, [user])

  useEffect(() => {
    fetchJobs(0)
  }, [fetchJobs])

  const handleDelete = async (jobId: string) => {
    setDeletingId(jobId)
    try {
      await deleteUserJob(jobId)
      setJobs((prev) => prev.filter((j) => j.job_id !== jobId))
      setTotal((prev) => Math.max(0, prev - 1))
      setConfirmDeleteId(null)
    } catch (err: any) {
      setError(err.message || 'Failed to delete article.')
    } finally {
      setDeletingId(null)
    }
  }

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString)
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      })
    } catch {
      return isoString
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'done':
        return (
          <span className="inline-flex items-center gap-1 text-[0.6875rem] font-semibold px-2 py-0.5 rounded-full bg-[var(--color-success-bg)] text-[var(--color-success)] border border-[var(--color-success)]/20">
            <CheckCircle2 className="w-3 h-3" />
            Completed
          </span>
        )
      case 'running':
        return (
          <span className="inline-flex items-center gap-1 text-[0.6875rem] font-semibold px-2 py-0.5 rounded-full bg-[var(--color-accent-muted)] text-[var(--color-accent)] border border-[var(--color-accent)]/20 animate-pulse">
            <Loader2 className="w-3 h-3 animate-spin" />
            In progress
          </span>
        )
      case 'error':
        return (
          <span className="inline-flex items-center gap-1 text-[0.6875rem] font-semibold px-2 py-0.5 rounded-full bg-[var(--color-error-bg)] text-[var(--color-error)] border border-[var(--color-error)]/20">
            <AlertCircle className="w-3 h-3" />
            Failed
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[0.6875rem] font-medium px-2 py-0.5 rounded-full bg-[var(--color-surface)] text-[var(--color-ink-3)] border border-[var(--color-border)]">
            <Clock className="w-3 h-3" />
            Queued
          </span>
        )
    }
  }

  return (
    <div
      className="min-h-[100dvh] flex flex-col"
      style={{ background: 'var(--color-canvas)' }}
    >
      <Header />

      <main className="flex-1 flex justify-center px-4 sm:px-6 py-8 sm:py-12">
        <div className="w-full max-w-4xl">

          {/* Page Title & Stats */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
            <div>
              <h1
                className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--color-ink)]"
                style={{ letterSpacing: '-0.025em' }}
              >
                Article History
              </h1>
              <p className="text-xs sm:text-sm text-[var(--color-ink-3)] mt-1">
                Your past research projects and presentation decks.
              </p>
            </div>

            <button
              type="button"
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-2 h-9 px-4 text-xs font-semibold rounded-lg bg-[var(--color-accent)] text-[var(--color-ink-inv)] hover:opacity-90 active:scale-[0.99] transition-all cursor-pointer self-start sm:self-auto focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
            >
              <Plus className="w-3.5 h-3.5" />
              New research
            </button>
          </div>

          {/* Not signed in state */}
          {(!user || !isConfigured) ? (
            <div className="p-8 sm:p-12 text-center rounded-xl border border-[var(--color-border)] bg-[var(--color-elevated)] space-y-4">
              <div className="w-12 h-12 rounded-full bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-center mx-auto text-[var(--color-ink-3)]">
                <FileText className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-[var(--color-ink)]">
                  Sign in to view history
                </h3>
                <p className="text-xs text-[var(--color-ink-3)] max-w-sm mx-auto mt-1">
                  Article history is automatically preserved when you are signed in to your SAGE account.
                </p>
              </div>
              {isConfigured && (
                <button
                  type="button"
                  onClick={() => setIsSignInOpen(true)}
                  className="inline-flex items-center gap-2 h-9 px-4 text-xs font-semibold rounded-lg bg-[var(--color-accent)] text-[var(--color-ink-inv)] hover:opacity-90 transition-all cursor-pointer focus:outline-none"
                >
                  Sign in
                </button>
              )}
            </div>
          ) : (
            <>
              {/* Error banner */}
              {error && (
                <div
                  role="alert"
                  className="flex items-start gap-2 p-3.5 mb-6 text-xs rounded-lg border border-[var(--color-error)]/20 bg-[var(--color-error-bg)] text-[var(--color-error)]"
                >
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <span>{error}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => fetchJobs(0)}
                    className="text-xs underline font-medium hover:opacity-80"
                  >
                    Retry
                  </button>
                </div>
              )}

              {/* Loading Skeleton */}
              {isLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="p-4 sm:p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-elevated)] animate-pulse flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                    >
                      <div className="space-y-2 flex-1">
                        <div className="h-4 bg-[var(--color-border-soft)] rounded w-2/3" />
                        <div className="h-3 bg-[var(--color-border-soft)] rounded w-1/4" />
                      </div>
                      <div className="h-8 bg-[var(--color-border-soft)] rounded w-20" />
                    </div>
                  ))}
                </div>
              ) : jobs.length === 0 ? (
                /* Empty state */
                <div className="p-8 sm:p-12 text-center rounded-xl border border-[var(--color-border)] bg-[var(--color-elevated)] space-y-4">
                  <div className="w-12 h-12 rounded-full bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-center mx-auto text-[var(--color-ink-3)]">
                    <FileText className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-[var(--color-ink)]">
                      No saved articles yet
                    </h3>
                    <p className="text-xs text-[var(--color-ink-3)] max-w-sm mx-auto mt-1">
                      Give SAGE a topic on the home page. Your completed research articles and slide decks will be saved here.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => navigate('/')}
                    className="inline-flex items-center gap-1.5 h-8 px-3.5 text-xs font-semibold rounded-lg bg-[var(--color-accent)] text-[var(--color-ink-inv)] hover:opacity-90 transition-all cursor-pointer focus:outline-none"
                  >
                    Create your first article
                  </button>
                </div>
              ) : (
                /* Article History List */
                <div className="space-y-3">
                  {jobs.map((item) => (
                    <div
                      key={item.job_id}
                      className="group p-4 sm:p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-elevated)] hover:border-[var(--color-border-strong)] transition-all shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                    >
                      {/* Topic & Metadata */}
                      <div className="space-y-1.5 flex-1 min-w-0 pr-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <button
                            type="button"
                            onClick={() => navigate(`/result/${item.job_id}`)}
                            className="text-left font-semibold text-sm sm:text-base text-[var(--color-ink)] hover:text-[var(--color-accent)] transition-colors truncate max-w-full focus:outline-none"
                          >
                            {item.topic || 'Untitled Article'}
                          </button>
                          {item.has_slides && (
                            <span className="inline-flex items-center gap-1 text-[0.625rem] font-semibold px-2 py-0.5 rounded bg-[var(--color-surface)] text-[var(--color-ink-2)] border border-[var(--color-border)]">
                              <Presentation className="w-3 h-3 text-[var(--color-accent)]" />
                              Slides ready
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-3 text-xs text-[var(--color-ink-3)] flex-wrap">
                          <span>{formatDate(item.created_at)}</span>
                          <span>·</span>
                          {getStatusBadge(item.status)}
                        </div>
                      </div>

                      {/* Action buttons */}
                      <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
                        <button
                          type="button"
                          onClick={() => navigate(`/result/${item.job_id}`)}
                          className="flex items-center gap-1.5 h-8 px-3 text-xs font-semibold rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-ink-2)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-ink)] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] cursor-pointer"
                        >
                          <span>Open</span>
                          <ExternalLink className="w-3 h-3 text-[var(--color-ink-3)]" />
                        </button>

                        {/* Delete button or confirmation */}
                        {confirmDeleteId === item.job_id ? (
                          <div className="flex items-center gap-1.5 bg-[var(--color-error-bg)] p-1 rounded-lg border border-[var(--color-error)]/20">
                            <span className="text-[0.6875rem] font-medium text-[var(--color-error)] px-1">
                              Delete?
                            </span>
                            <button
                              type="button"
                              onClick={() => handleDelete(item.job_id)}
                              disabled={deletingId === item.job_id}
                              className="h-6 px-2 text-[0.6875rem] font-semibold rounded bg-[var(--color-error)] text-white hover:opacity-90 disabled:opacity-50"
                            >
                              {deletingId === item.job_id ? '...' : 'Yes'}
                            </button>
                            <button
                              type="button"
                              onClick={() => setConfirmDeleteId(null)}
                              className="h-6 px-2 text-[0.6875rem] font-medium rounded text-[var(--color-ink-3)] hover:text-[var(--color-ink)]"
                            >
                              No
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteId(item.job_id)}
                            aria-label="Delete article"
                            className="p-2 text-[var(--color-ink-4)] hover:text-[var(--color-error)] hover:bg-[var(--color-surface)] rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Load more */}
                  {jobs.length < total && (
                    <div className="pt-4 text-center">
                      <button
                        type="button"
                        onClick={() => fetchJobs(pageOffset + PAGE_SIZE, true)}
                        disabled={isLoadingMore}
                        className="inline-flex items-center gap-2 h-9 px-4 text-xs font-semibold rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-ink)] hover:bg-[var(--color-border-soft)] disabled:opacity-50 transition-colors cursor-pointer focus:outline-none"
                      >
                        {isLoadingMore && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                        {isLoadingMore ? 'Loading...' : `Load more (${total - jobs.length} remaining)`}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

        </div>
      </main>
    </div>
  )
}
