import { useEffect, useRef, useState } from 'react'
import { type BlogResult, type JobStatus, getJobResult, getJobStatus } from '@/api/client'

interface UseJobStatusResult {
  status: JobStatus | null
  result: BlogResult | null
  isLoading: boolean
  error: string | null
}

export function useJobStatus(jobId: string | null): UseJobStatusResult {
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [result, setResult] = useState<BlogResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!jobId) return

    setIsLoading(true)
    setError(null)
    setResult(null)
    setStatus(null)

    const poll = async () => {
      try {
        const jobStatus = await getJobStatus(jobId)
        setStatus(jobStatus)

        if (jobStatus.status === 'done') {
          clearInterval(intervalRef.current!)
          const blogResult = await getJobResult(jobId)
          setResult(blogResult)
          setIsLoading(false)
        } else if (jobStatus.status === 'error') {
          clearInterval(intervalRef.current!)
          setError(jobStatus.error ?? 'Generation failed. Please try again.')
          setIsLoading(false)
        }
      } catch (err) {
        clearInterval(intervalRef.current!)
        setError(err instanceof Error ? err.message : 'Failed to reach the server.')
        setIsLoading(false)
      }
    }

    // Poll immediately, then every 2s
    void poll()
    intervalRef.current = setInterval(() => void poll(), 2000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [jobId])

  return { status, result, isLoading, error }
}
