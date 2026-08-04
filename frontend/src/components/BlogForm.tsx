import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Globe, BookOpen, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-6">
      {/* Topic */}
      <div className="space-y-2">
        <Label htmlFor="topic" className="text-slate-300 font-medium">
          Topic <span className="text-purple-400">*</span>
        </Label>
        <Textarea
          id="topic"
          placeholder="e.g. How LangGraph enables stateful multi-agent workflows in production"
          className="min-h-[100px] resize-none bg-white/5 border-white/10 text-white placeholder:text-slate-500 focus-visible:ring-purple-500 focus-visible:border-purple-500/50 text-base rounded-xl"
          value={form.topic}
          onChange={e => setForm(f => ({ ...f, topic: e.target.value }))}
          required
        />
      </div>

      {/* Row: Tone + Style */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label className="text-slate-300 font-medium">Tone</Label>
          <Select value={form.tone} onValueChange={v => setForm(f => ({ ...f, tone: v }))}>
            <SelectTrigger className="bg-white/5 border-white/10 text-white focus:ring-purple-500 rounded-xl">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#1a1a28] border-white/10 text-white">
              {TONES.map(t => (
                <SelectItem key={t} value={t} className="capitalize focus:bg-purple-500/20">
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label className="text-slate-300 font-medium">Style</Label>
          <Select value={form.style} onValueChange={v => setForm(f => ({ ...f, style: v as GenerateRequest['style'] }))}>
            <SelectTrigger className="bg-white/5 border-white/10 text-white focus:ring-purple-500 rounded-xl">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#1a1a28] border-white/10 text-white">
              {STYLES.map(s => (
                <SelectItem key={s.value} value={s.value} className="focus:bg-purple-500/20">
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Row: Audience + Length */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="audience" className="text-slate-300 font-medium">Audience</Label>
          <input
            id="audience"
            type="text"
            placeholder="e.g. developers, product managers..."
            className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500/50 text-sm"
            value={form.audience}
            onChange={e => setForm(f => ({ ...f, audience: e.target.value }))}
          />
        </div>

        <div className="space-y-2">
          <Label className="text-slate-300 font-medium">Length</Label>
          <Select value={form.length} onValueChange={v => setForm(f => ({ ...f, length: v as GenerateRequest['length'] }))}>
            <SelectTrigger className="bg-white/5 border-white/10 text-white focus:ring-purple-500 rounded-xl">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#1a1a28] border-white/10 text-white">
              {LENGTHS.map(l => (
                <SelectItem key={l.value} value={l.value} className="focus:bg-purple-500/20">
                  {l.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Web research toggle */}
      <div className="flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/10">
        <div className="flex items-center gap-3">
          {form.use_web
            ? <Globe className="h-5 w-5 text-cyan-400" />
            : <BookOpen className="h-5 w-5 text-slate-400" />
          }
          <div>
            <p className="text-slate-200 font-medium text-sm">Web Research</p>
            <p className="text-slate-500 text-xs">
              {form.use_web
                ? 'Searches the web for up-to-date sources and citations'
                : 'Uses model knowledge only (evergreen topics)'}
            </p>
          </div>
        </div>
        <Switch
          id="use_web"
          checked={form.use_web}
          onCheckedChange={v => setForm(f => ({ ...f, use_web: v }))}
          className="data-[state=checked]:bg-purple-500"
        />
      </div>

      {error && (
        <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
          {error}
        </p>
      )}

      <Button
        type="submit"
        disabled={isSubmitting || !form.topic.trim()}
        className="w-full h-12 text-base font-semibold rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-500 hover:to-violet-500 text-white border-0 shadow-lg shadow-purple-500/25 transition-all duration-200 hover:shadow-purple-500/40 hover:scale-[1.01] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Starting…
          </>
        ) : (
          <>
            <Sparkles className="mr-2 h-5 w-5" />
            Generate Blog
          </>
        )}
      </Button>
    </form>
  )
}
