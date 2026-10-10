import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Globe, BookOpen, Loader2, PenLine } from 'lucide-react'
import { generateBlog, type GenerateRequest } from '@/api/client'

const TONES = ['professional', 'casual', 'conversational', 'technical', 'academic', 'friendly']
const LENGTHS = [
  { value: 'short', label: 'Short (~800 words)' },
  { value: 'medium', label: 'Medium (~1,500 words)' },
  { value: 'long', label: 'Long (~2,500 words)' },
]
const STYLES = [
  { value: 'blog', label: 'Blog Post' },
  { value: 'tutorial', label: 'Tutorial' },
  { value: 'explainer', label: 'Explainer' },
  { value: 'comparison', label: 'Comparison' },
  { value: 'news_roundup', label: 'News Roundup' },
]

/* Shared radius — restrained, not pill-heavy */
const R = '4px'

function FieldLabel({ children, htmlFor }: { children: React.ReactNode; htmlFor?: string }) {
  return (
    <label
      htmlFor={htmlFor}
      className="block text-sm font-medium mb-1.5"
      style={{ color: 'var(--color-ink-2)' }}
    >
      {children}
    </label>
  )
}

function SelectField({
  value,
  onChange,
  options,
  id,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  id?: string
}) {
  return (
    <select
      id={id}
      value={value}
      onChange={e => onChange(e.target.value)}
      className="w-full h-10 px-3 text-sm appearance-none cursor-pointer transition-colors"
      style={{
        borderRadius: R,
        background: 'var(--color-canvas)',
        border: '1px solid var(--color-border)',
        color: 'var(--color-ink)',
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239c9890' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right 10px center',
        paddingRight: '2rem',
      }}
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

export default function BlogForm() {
  const navigate = useNavigate()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [form, setForm] = useState<GenerateRequest>({
    topic: '',
    tone: 'professional',
    length: 'medium',
    style: 'blog',
    audience: 'developers',
    use_web: true,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.topic.trim()) return

    setIsSubmitting(true)
    setError(null)
    try {
      const { job_id } = await generateBlog(form)
      navigate(`/result/${job_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect to the server.')
      setIsSubmitting(false)
    }
  }

  const toneOptions = TONES.map(t => ({ value: t, label: t.charAt(0).toUpperCase() + t.slice(1) }))

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-5">
      {/* Topic */}
      <div>
        <FieldLabel htmlFor="topic">
          Topic <span style={{ color: 'var(--color-accent)' }}>*</span>
        </FieldLabel>
        <textarea
          id="topic"
          placeholder="e.g. How LangGraph enables stateful multi-agent workflows in production"
          rows={3}
          className="w-full px-3 py-2.5 text-sm resize-none transition-colors"
          style={{
            borderRadius: R,
            background: 'var(--color-canvas)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-ink)',
          }}
          value={form.topic}
          onChange={e => setForm(f => ({ ...f, topic: e.target.value }))}
          required
        />
      </div>

      {/* Tone + Style */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <FieldLabel>Tone</FieldLabel>
          <SelectField
            value={form.tone}
            onChange={v => setForm(f => ({ ...f, tone: v }))}
            options={toneOptions}
          />
        </div>
        <div>
          <FieldLabel>Style</FieldLabel>
          <SelectField
            value={form.style}
            onChange={v => setForm(f => ({ ...f, style: v as GenerateRequest['style'] }))}
            options={STYLES}
          />
        </div>
      </div>

      {/* Audience + Length */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <FieldLabel htmlFor="audience">Audience</FieldLabel>
          <input
            id="audience"
            type="text"
            placeholder="e.g. developers"
            className="w-full h-10 px-3 text-sm transition-colors"
            style={{
              borderRadius: R,
              background: 'var(--color-canvas)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-ink)',
            }}
            value={form.audience}
            onChange={e => setForm(f => ({ ...f, audience: e.target.value }))}
          />
        </div>
        <div>
          <FieldLabel>Length</FieldLabel>
          <SelectField
            value={form.length}
            onChange={v => setForm(f => ({ ...f, length: v as GenerateRequest['length'] }))}
            options={LENGTHS}
          />
        </div>
      </div>

      {/* Web research toggle row */}
      <div
        className="flex items-center justify-between px-3.5 py-3"
        style={{
          borderRadius: R,
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="flex items-center gap-2.5">
          {form.use_web
            ? <Globe className="h-4 w-4" style={{ color: 'var(--color-accent)' }} />
            : <BookOpen className="h-4 w-4" style={{ color: 'var(--color-ink-4)' }} />
          }
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--color-ink)' }}>Web Research</p>
            <p className="text-xs" style={{ color: 'var(--color-ink-4)' }}>
              {form.use_web
                ? 'Searches the web for up-to-date sources'
                : 'Uses model knowledge only'}
            </p>
          </div>
        </div>
        {/*
          Toggle: track stays pill-shaped (rounded-full) because the sliding
          thumb's circular shape depends on it — this is a functional, not
          decorative, use of the pill shape.
        */}
        <button
          type="button"
          role="switch"
          aria-checked={form.use_web}
          onClick={() => setForm(f => ({ ...f, use_web: !f.use_web }))}
          className="relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors"
          style={{
            background: form.use_web ? 'var(--color-accent)' : 'var(--color-border-strong)',
          }}
        >
          <span
            className="inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform"
            style={{ transform: form.use_web ? 'translateX(18px)' : 'translateX(3px)' }}
          />
        </button>
      </div>

      {error && (
        <p
          className="text-sm px-3.5 py-3"
          style={{
            borderRadius: R,
            color: 'var(--color-error)',
            background: 'var(--color-error-bg)',
            border: '1px solid rgba(192,57,43,0.2)',
          }}
        >
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={isSubmitting || !form.topic.trim()}
        className="w-full h-11 flex items-center justify-center gap-2 text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        style={{
          borderRadius: R,
          background: isSubmitting || !form.topic.trim() ? 'var(--color-border-strong)' : 'var(--color-ink)',
          color: 'var(--color-ink-inv)',
          border: 'none',
        }}
      >
        {isSubmitting ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Starting…
          </>
        ) : (
          <>
            <PenLine className="h-4 w-4" />
            Generate Article
          </>
        )}
      </button>
    </form>
  )
}
