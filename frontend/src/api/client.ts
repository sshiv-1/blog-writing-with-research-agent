import { supabase } from '@/lib/supabase'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.trim() || 'http://localhost:8000'

// ── Request / Response types ─────────────────────────────────────────────────

export interface GenerateRequest {
  topic: string
  tone: string
  length: 'short' | 'medium' | 'long'
  style: 'blog' | 'tutorial' | 'explainer' | 'news_roundup' | 'comparison'
  audience: string
  use_web: boolean
}

export interface GenerateResponse {
  job_id: string
  status: string
}

export interface JobStatus {
  job_id: string
  status: 'queued' | 'running' | 'done' | 'error'
  stage: string
  progress: number
  error?: string
}

export interface OutlineSection {
  id: number
  title: string
  goal: string
  bullets: string[]
  target_words: number
  tags: string[]
  requires_research: boolean
  requires_citations: boolean
  requires_code: boolean
}

export interface Source {
  title: string
  url: string
  published_at?: string
  snippet?: string
  source?: string
}

export interface BlogResult {
  title: string
  outline: OutlineSection[]
  draft: string
  sources: Source[]
}

export interface StartSlidesRequest {
  slide_count?: number
  audience?: string
}

export interface SlideJobStatus {
  job_id: string
  status: 'queued' | 'running' | 'done' | 'error'
  stage: string
  progress: number
  slide_count?: number
  warnings: string[]
  error?: string | null
}

export interface UserJobItem {
  job_id: string
  topic: string
  status: 'queued' | 'running' | 'done' | 'error'
  stage: string
  progress: number
  created_at: string
  has_slides: boolean
}

export interface PaginatedUserJobs {
  items: UserJobItem[]
  total: number
  limit: number
  offset: number
}

export interface UserKeyItem {
  provider: string
  last4: string
  created_at?: string
}

export interface LLMTestResponse {
  ok: boolean
  provider: string
  model: string
  error?: string | null
}

export class ApiError extends Error {
  status: number
  detail?: string
  constructor(status: number, message: string, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

// ── Auth Token Helper (dynamic at request time) ───────────────────────────────

export async function getAuthToken(): Promise<string | null> {
  if (!supabase) return null
  try {
    const { data, error } = await supabase.auth.getSession()
    if (error || !data.session) return null
    return data.session.access_token
  } catch {
    return null
  }
}

// ── Central Authenticated Request Helper ─────────────────────────────────────

function formatApiError(status: number, bodyText: string): { message: string; detail?: string } {
  let detail = ''
  try {
    const parsed = JSON.parse(bodyText)
    detail = parsed.detail || parsed.message || ''
  } catch {
    detail = bodyText.trim()
  }

  let message = `Request failed (${status})`
  if (status === 400) {
    message = detail || 'Invalid request or missing API key.'
  } else if (status === 401) {
    message = 'Session expired or invalid authentication. Please sign in again.'
  } else if (status === 404) {
    message = detail || 'Article or resource not found or no longer available.'
  } else if (status === 409) {
    message = detail || 'Operation cannot be completed yet. Job still in progress.'
  } else if (status === 429) {
    message = detail || 'Rate limit reached. Please wait a moment or configure your own API key.'
  } else if (detail) {
    message = detail
  }

  return { message, detail }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getAuthToken()
  const headers = new Headers(options?.headers || {})

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const bodyText = await res.text().catch(() => '')
    const { message, detail } = formatApiError(res.status, bodyText)
    throw new ApiError(res.status, message, detail)
  }

  return res.json() as Promise<T>
}

// ── Blog Endpoints ───────────────────────────────────────────────────────────

export function generateBlog(
  req: GenerateRequest,
  byokHeaders?: Record<string, string>,
): Promise<GenerateResponse> {
  return request<GenerateResponse>('/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(byokHeaders || {}),
    },
    body: JSON.stringify(req),
  })
}

export function getJobStatus(jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`/jobs/${jobId}`)
}

export function getJobResult(jobId: string): Promise<BlogResult> {
  return request<BlogResult>(`/jobs/${jobId}/result`)
}

// ── Slide Endpoints ──────────────────────────────────────────────────────────

export function startSlides(
  jobId: string,
  req?: StartSlidesRequest,
  byokHeaders?: Record<string, string>,
): Promise<SlideJobStatus> {
  return request<SlideJobStatus>(`/jobs/${jobId}/slides`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(byokHeaders || {}),
    },
    body: JSON.stringify(req ?? {}),
  })
}

export async function getSlidesStatus(jobId: string): Promise<SlideJobStatus | null> {
  try {
    return await request<SlideJobStatus>(`/jobs/${jobId}/slides`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return null
    }
    throw err
  }
}

export function slidesDownloadUrl(jobId: string, format: 'pdf' | 'pptx' | 'tex'): string {
  return `${API_BASE}/jobs/${jobId}/slides/download?format=${format}`
}

// ── Authenticated Download & PDF Streamer ─────────────────────────────────────

export async function fetchPdfBlob(jobId: string): Promise<{ blob: Blob; url: string }> {
  const token = await getAuthToken()
  const headers = new Headers()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(slidesDownloadUrl(jobId, 'pdf'), { headers })
  if (!res.ok) {
    const bodyText = await res.text().catch(() => '')
    const { message } = formatApiError(res.status, bodyText)
    throw new ApiError(res.status, message)
  }

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  return { blob, url }
}

export async function downloadSlideArtifact(
  jobId: string,
  format: 'pdf' | 'pptx' | 'tex',
  fallbackTitle: string = 'slides',
): Promise<void> {
  const token = await getAuthToken()
  const headers = new Headers()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(slidesDownloadUrl(jobId, format), { headers })
  if (!res.ok) {
    const bodyText = await res.text().catch(() => '')
    const { message } = formatApiError(res.status, bodyText)
    throw new ApiError(res.status, message)
  }

  // Extract filename from Content-Disposition header
  const disposition = res.headers.get('Content-Disposition')
  let filename = `${fallbackTitle}.${format}`
  if (disposition) {
    const match = disposition.match(/filename="?([^"]+)"?/)
    if (match && match[1]) {
      filename = match[1]
    }
  }

  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  try {
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } finally {
    setTimeout(() => {
      URL.revokeObjectURL(objectUrl)
    }, 1000)
  }
}

// ── Authenticated History & Account Keys Endpoints ───────────────────────────

export function getUserJobs(limit: number = 20, offset: number = 0): Promise<PaginatedUserJobs> {
  return request<PaginatedUserJobs>(`/me/jobs?limit=${limit}&offset=${offset}`)
}

export function deleteUserJob(jobId: string): Promise<{ ok: boolean; job_id: string }> {
  return request<{ ok: boolean; job_id: string }>(`/jobs/${jobId}`, {
    method: 'DELETE',
  })
}

export function getUserSavedKeys(): Promise<UserKeyItem[]> {
  return request<UserKeyItem[]>('/me/keys')
}

export function saveUserKey(
  provider: string,
  apiKey: string,
): Promise<{ ok: boolean; provider: string; last4: string }> {
  return request<{ ok: boolean; provider: string; last4: string }>(`/me/keys/${provider}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey }),
  })
}

export function deleteUserKey(provider: string): Promise<{ ok: boolean; provider: string }> {
  return request<{ ok: boolean; provider: string }>(`/me/keys/${provider}`, {
    method: 'DELETE',
  })
}

// ── BYOK Connection Test ─────────────────────────────────────────────────────

export function testLlmConnection(headers: Record<string, string>): Promise<LLMTestResponse> {
  return request<LLMTestResponse>('/llm/test', {
    method: 'POST',
    headers,
  })
}
