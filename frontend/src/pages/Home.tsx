import { Sparkles, Zap, BookOpen, Globe2 } from 'lucide-react'
import BlogForm from '@/components/BlogForm'

const FEATURES = [
  { icon: Globe2, label: 'Live web research', desc: 'Pulls fresh sources via Tavily' },
  { icon: Zap, label: 'Parallel writing', desc: 'All sections drafted simultaneously' },
  { icon: BookOpen, label: 'Cited sources', desc: 'Every claim backed by evidence' },
]

export default function Home() {
  return (
    <div className="min-h-screen bg-[#09090b] relative overflow-hidden">
      {/* Background ambient glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 80% 50% at 50% -10%, rgba(124,58,237,0.18) 0%, transparent 60%), ' +
            'radial-gradient(ellipse 60% 40% at 80% 80%, rgba(6,182,212,0.08) 0%, transparent 60%)',
        }}
      />

      {/* Subtle grid */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.025]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative z-10 flex flex-col items-center px-4 py-16 sm:py-24">
        {/* Hero */}
        <div className="text-center max-w-2xl mb-14">
          {/* Pill badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-300 text-xs font-medium mb-6">
            <Sparkles className="h-3.5 w-3.5" />
            Powered by LangGraph + Gemini
          </div>

          <h1
            className="text-5xl sm:text-6xl font-bold tracking-tight mb-5"
            style={{
              background: 'linear-gradient(135deg, #f8fafc 0%, #c4b5fd 50%, #67e8f9 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            Blog Writing
            <br />
            Agent
          </h1>

          <p className="text-slate-400 text-lg leading-relaxed max-w-xl mx-auto">
            Enter a topic and get a fully researched, structured blog post — complete with
            live sources, a custom outline, and parallel section drafting.
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap justify-center gap-3 mt-8">
            {FEATURES.map(f => (
              <div
                key={f.label}
                className="flex items-center gap-2 px-4 py-2 rounded-xl border border-white/8 bg-white/[0.03] text-sm"
              >
                <f.icon className="h-4 w-4 text-purple-400" />
                <span className="text-slate-300 font-medium">{f.label}</span>
                <span className="text-slate-500 hidden sm:inline">— {f.desc}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Form card */}
        <div
          className="w-full max-w-xl rounded-2xl border border-white/[0.08] p-8"
          style={{
            background:
              'linear-gradient(135deg, rgba(26,26,40,0.9) 0%, rgba(17,17,24,0.95) 100%)',
            backdropFilter: 'blur(20px)',
            boxShadow:
              '0 0 0 1px rgba(124,58,237,0.1), 0 25px 50px rgba(0,0,0,0.5), 0 0 80px rgba(124,58,237,0.06)',
          }}
        >
          <h2 className="text-lg font-semibold text-white mb-6">Configure your blog</h2>
          <BlogForm />
        </div>
      </div>
    </div>
  )
}
