const API_BASE = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000'

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

// ── API helpers ───────────────────────────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${body ? ': ' + body : ''}`)
  }
  return res.json() as Promise<T>
}

export function generateBlog(req: GenerateRequest): Promise<GenerateResponse> {
  return request<GenerateResponse>('/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
}

export function getJobStatus(jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`/jobs/${jobId}`)
}

export function getJobResult(jobId: string): Promise<BlogResult> {
  return request<BlogResult>(`/jobs/${jobId}/result`)
}
