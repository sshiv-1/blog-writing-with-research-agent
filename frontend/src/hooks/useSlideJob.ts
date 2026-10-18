import { useEffect, useRef, useState, useCallback } from 'react'
import {
  type SlideJobStatus,
  type StartSlidesRequest,
  getSlidesStatus,
  startSlides,
  fetchPdfBlob,
} from '@/api/client'

export interface UseSlideJobResult {
  status: SlideJobStatus | null
  isLoading: boolean
  error: string | null
  pdfBlobUrl: string | null
  isPdfLoading: boolean
  pdfError: string | null
  start: (options?: StartSlidesRequest, byokHeaders?: Record<string, string>) => Promise<void>
  retryPdf: () => Promise<void>
}

export function useSlideJob(jobId: string | null): UseSlideJobResult {
  const [status, setStatus] = useState<SlideJobStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null)
  const [isPdfLoading, setIsPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isPollingRef = useRef(false)
  const inFlightRef = useRef(false)
  const pdfBlobUrlRef = useRef<string | null>(null)

  const clearPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    isPollingRef.current = false
  }, [])

  const fetchPdf = useCallback(async (targetJobId: string) => {
    setIsPdfLoading(true)
    setPdfError(null)
    try {
      const { url } = await fetchPdfBlob(targetJobId)

      if (pdfBlobUrlRef.current) {
        URL.revokeObjectURL(pdfBlobUrlRef.current)
      }
      pdfBlobUrlRef.current = url
      setPdfBlobUrl(url)
    } catch (err) {
      setPdfError(err instanceof Error ? err.message : 'Failed to load PDF preview.')
    } finally {
      setIsPdfLoading(false)
    }
  }, [])

  const startPolling = useCallback((targetJobId: string) => {
    if (isPollingRef.current) return
    isPollingRef.current = true

    const poll = async () => {
      if (inFlightRef.current) return
      inFlightRef.current = true
      try {
        const currentStatus = await getSlidesStatus(targetJobId)
        if (!currentStatus) {
          // 404: backend restarted and job is gone
          clearPolling()
          setStatus(null)
          setError(null)
          setIsLoading(false)
          return
        }

        setStatus(currentStatus)

        if (currentStatus.status === 'done') {
          clearPolling()
          setIsLoading(false)
          void fetchPdf(targetJobId)
        } else if (currentStatus.status === 'error') {
          clearPolling()
          setIsLoading(false)
          setError(currentStatus.error || 'Slide generation failed.')
        }
      } catch (err) {
        clearPolling()
        setIsLoading(false)
        setError(err instanceof Error ? err.message : 'Failed to check slide generation status.')
      } finally {
        inFlightRef.current = false
      }
    }

    intervalRef.current = setInterval(() => {
      void poll()
    }, 2000)
  }, [clearPolling, fetchPdf])

  // Initial mount check
  useEffect(() => {
    if (!jobId) return

    let cancelled = false

    const checkInitial = async () => {
      try {
        const initialStatus = await getSlidesStatus(jobId)
        if (cancelled) return

        if (!initialStatus) {
          // 404: no slide job yet -> show empty state, not an error
          setStatus(null)
          return
        }

        setStatus(initialStatus)

        if (initialStatus.status === 'queued' || initialStatus.status === 'running') {
          setIsLoading(true)
          startPolling(jobId)
        } else if (initialStatus.status === 'done') {
          void fetchPdf(jobId)
        } else if (initialStatus.status === 'error') {
          setError(initialStatus.error || 'Slide generation failed.')
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load slide status.')
        }
      }
    }

    void checkInitial()

    return () => {
      cancelled = true
      clearPolling()
      if (pdfBlobUrlRef.current) {
        URL.revokeObjectURL(pdfBlobUrlRef.current)
        pdfBlobUrlRef.current = null
      }
    }
  }, [jobId, clearPolling, fetchPdf, startPolling])

  const start = useCallback(async (options?: StartSlidesRequest, byokHeaders?: Record<string, string>) => {
    if (!jobId) return

    setIsLoading(true)
    setError(null)
    setPdfError(null)

    try {
      const initialStatus = await startSlides(jobId, options, byokHeaders)
      setStatus(initialStatus)
      startPolling(jobId)
    } catch (err) {
      setIsLoading(false)
      setError(err instanceof Error ? err.message : 'Failed to start slide generation.')
    }
  }, [jobId, startPolling])

  const retryPdf = useCallback(async () => {
    if (!jobId) return
    await fetchPdf(jobId)
  }, [jobId, fetchPdf])

  return {
    status,
    isLoading,
    error,
    pdfBlobUrl,
    isPdfLoading,
    pdfError,
    start,
    retryPdf,
  }
}
