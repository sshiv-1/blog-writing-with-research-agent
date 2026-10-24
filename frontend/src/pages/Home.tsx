import BlogForm from '@/components/BlogForm'
import Header from '@/components/Header'
import { useAuth } from '@/context/AuthContext'
import { useModelSettings } from '@/context/ModelSettingsContext'

export default function Home() {
  const { user, isConfigured } = useAuth()
  const { setIsSignInOpen } = useModelSettings()

  return (
    <div
      className="min-h-[100dvh] flex flex-col"
      style={{ background: 'var(--color-canvas)' }}
    >
      <Header />

      {/* Main — split layout at lg, stacked on mobile */}
      <main className="flex-1 flex items-start justify-center px-6 py-12 sm:py-16">
        <div className="w-full max-w-6xl">
          {/* Grid: left copy & features, right form card */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_440px] gap-12 lg:gap-16 items-start">

            {/* ── Left: intro copy & features ── */}
            <div className="pt-2 lg:pt-4">
              <h1
                className="text-[2.75rem] sm:text-[3.5rem] lg:text-[4.25rem] font-light leading-[1.02] mb-5 tracking-tight"
                style={{
                  fontFamily: 'var(--font-display)',
                  color: 'var(--color-ink)',
                  letterSpacing: '-0.015em',
                }}
              >
                Research it. Write it.
                <span
                  style={{
                    display: 'block',
                    fontFamily: 'var(--font-editorial)',
                    fontStyle: 'italic',
                    fontWeight: 400,
                    color: 'var(--color-ink-3)',
                    marginTop: '0.12em',
                    letterSpacing: '-0.01em',
                  }}
                >
                  Present it.
                </span>
              </h1>

              <p
                className="text-base leading-relaxed mb-6 max-w-[50ch]"
                style={{
                  fontFamily: 'var(--font-body)',
                  color: 'var(--color-ink-3)',
                  fontSize: '1.0625rem',
                  lineHeight: 1.65,
                }}
              >
                Give SAGE a topic. It researches the web, plans an outline, drafts every section in parallel, and delivers a cited article. Then turn that article into a lecture-style slide deck with one click: a PDF and an editable PowerPoint.
              </p>

              {/* Capability chips */}
              <div className="flex flex-wrap gap-2 mb-8">
                {[
                  { label: 'Live web research', detail: 'Tavily' },
                  { label: 'Parallel drafting', detail: 'LangGraph' },
                  { label: 'Cited sources', detail: 'Every claim' },
                  { label: 'Lecture slides', detail: 'PDF + PPTX' },
                ].map(({ label, detail }) => (
                  <span
                    key={label}
                    className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 transition-colors hover:border-[var(--color-border-strong)] cursor-default"
                    style={{
                      fontFamily: 'var(--font-ui)',
                      background: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                      color: 'var(--color-ink-3)',
                      borderRadius: '4px',
                    }}
                  >
                    {label}
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-ink-4)', fontWeight: 400 }}>· {detail}</span>
                  </span>
                ))}
              </div>

              {/* Compact "How it works" strip */}
              <div className="mb-8">
                <p
                  className="text-[11px] font-medium uppercase mb-3"
                  style={{
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--color-ink-4)',
                    letterSpacing: '0.08em',
                  }}
                >
                  How it works
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {[
                    { step: '1', title: 'Topic', desc: 'Set tone, audience and length' },
                    { step: '2', title: 'Research', desc: 'Web search and evidence' },
                    { step: '3', title: 'Article', desc: 'Outline, parallel drafting, citations' },
                    { step: '4', title: 'Slides', desc: 'Beamer PDF and editable PPTX' },
                  ].map(({ step, title, desc }) => (
                    <div
                      key={step}
                      className="flex items-start gap-2.5 p-2.5 transition-colors hover:border-[var(--color-border-strong)]"
                      style={{
                        borderRadius: '4px',
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                      }}
                    >
                      <span
                        className="flex-shrink-0 w-5 h-5 flex items-center justify-center text-[11px] font-semibold"
                        style={{
                          fontFamily: 'var(--font-mono)',
                          borderRadius: '3px',
                          background: 'var(--color-elevated)',
                          color: 'var(--color-accent)',
                          border: '1px solid var(--color-border)',
                        }}
                      >
                        {step}
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold leading-none mb-1" style={{ fontFamily: 'var(--font-ui)', color: 'var(--color-ink)' }}>
                          {title}
                        </p>
                        <p className="text-[11px] leading-snug" style={{ fontFamily: 'var(--font-body)', color: 'var(--color-ink-3)' }}>
                          {desc}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Purely decorative 16:9 slide-preview mock */}
              <div className="hidden sm:block max-w-[280px] w-full mb-8">
                <div
                  className="relative aspect-[16/9] w-full overflow-hidden flex flex-col justify-between"
                  style={{
                    borderRadius: '6px',
                    background: 'var(--color-elevated)',
                    border: '1px solid var(--color-border)',
                    boxShadow: '0 2px 8px rgba(26,25,22,0.06)',
                  }}
                >
                  {/* Navy title bar */}
                  <div
                    className="px-3 py-1.5 flex items-center justify-between"
                    style={{ background: '#272A40' }}
                  >
                    <span className="text-[10px] font-medium text-white tracking-tight" style={{ fontFamily: 'var(--font-ui)' }}>Key Insight</span>
                    <span className="text-[8px] text-[#DCEEEE]" style={{ fontFamily: 'var(--font-mono)' }}>03 / 10</span>
                  </div>

                  {/* Body with placeholder lines */}
                  <div className="p-3 space-y-1.5 flex-1 flex flex-col justify-center">
                    <div className="h-1.5 w-11/12 rounded" style={{ background: '#e5e2db' }} />
                    <div className="h-1.5 w-4/5 rounded" style={{ background: '#ede9e3' }} />
                    <div className="h-1.5 w-3/4 rounded" style={{ background: '#ede9e3' }} />
                  </div>

                  {/* Tiny navy footer bar */}
                  <div
                    className="px-3 py-0.5 flex items-center justify-between text-[7px] text-white"
                    style={{ background: '#272A40' }}
                  >
                    <span className="font-semibold" style={{ fontFamily: 'var(--font-ui)' }}>SAGE</span>
                    <span className="opacity-80" style={{ fontFamily: 'var(--font-mono)' }}>Lecture Series</span>
                  </div>
                </div>
              </div>

              {/* Footer note — visible on desktop */}
              <p
                className="text-xs hidden lg:block"
                style={{
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--color-ink-4)',
                  marginTop: '1.5rem',
                  letterSpacing: '0.02em',
                }}
              >
                Powered by LangGraph + Groq · Tavily web search
              </p>
            </div>

            {/* ── Right: form card ── */}
            <div
              className="w-full"
              style={{
                background: 'var(--color-elevated)',
                border: '1px solid var(--color-border)',
                borderRadius: '6px',
                boxShadow: '0 1px 3px rgba(26,25,22,0.06), 0 8px 24px rgba(26,25,22,0.05)',
              }}
            >
              {/* Form header */}
              <div
                className="px-6 py-4"
                style={{ borderBottom: '1px solid var(--color-border)' }}
              >
                <p
                  className="text-xs font-medium uppercase"
                  style={{
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--color-ink-4)',
                    letterSpacing: '0.09em',
                  }}
                >
                  Article Settings
                </p>
              </div>
              {/* Form body */}
              <div className="px-6 py-6">
                <BlogForm />
              </div>
            </div>

            {/* Guest note under form card */}
            {!user && isConfigured && (
              <p className="text-center text-xs text-[var(--color-ink-3)] -mt-8 mb-4 lg:mb-0" style={{ fontFamily: 'var(--font-body)' }}>
                <button
                  type="button"
                  onClick={() => setIsSignInOpen(true)}
                  className="text-[var(--color-accent)] hover:underline font-medium cursor-pointer"
                  style={{ fontFamily: 'var(--font-ui)' }}
                >
                  Sign in
                </button>{' '}
                to save your history and keys.
              </p>
            )}

          </div>
        </div>
      </main>

      {/* Mobile footer */}
      <p
        className="text-xs text-center pb-6 lg:hidden"
        style={{
          fontFamily: 'var(--font-mono)',
          color: 'var(--color-ink-4)',
          letterSpacing: '0.02em',
        }}
      >
        Powered by LangGraph + Groq · Tavily web search
      </p>
    </div>
  )
}
