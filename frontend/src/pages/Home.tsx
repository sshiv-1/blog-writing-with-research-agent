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

      <main className="flex-1 flex items-start justify-center px-5 py-10 sm:px-6 sm:py-12">
        <div className="w-full max-w-7xl">
          {/* Grid: left copy & features, right form card */}
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_440px] gap-10 lg:gap-16 items-start">

            {/* ── Left: intro copy & features ── */}
            <div className="pt-2 lg:pt-4 min-w-0">
              <h1
                className="text-[2.5rem] sm:text-6xl lg:text-7xl font-normal leading-[1.04] mb-5"
                style={{
                  fontFamily: 'var(--font-display)',
                  color: 'var(--color-ink)',
                  letterSpacing: '-0.025em',
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
                    marginTop: '0.08em',
                    letterSpacing: '-0.015em',
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
                  fontSize: '1.125rem',
                  lineHeight: 1.6,
                }}
              >
                Give SAGE a topic. It researches the web, plans an outline, drafts every section in parallel, and delivers a cited article. Then turn that article into a lecture-style slide deck with one click: a PDF and an editable PowerPoint.
              </p>

              <div className="mb-8">
                <h2
                  className="text-lg font-medium mb-3"
                  style={{ fontFamily: 'var(--font-ui)', color: 'var(--color-ink)' }}
                >
                  How it works
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
                  {[
                    { step: '1', title: 'Topic', desc: 'Set tone, audience and length' },
                    { step: '2', title: 'Research', desc: 'Web search and evidence' },
                    { step: '3', title: 'Article', desc: 'Outline, parallel drafting, citations' },
                    { step: '4', title: 'Slides', desc: 'Beamer PDF and editable PPTX' },
                  ].map(({ step, title, desc }) => (
                    <div
                      key={step}
                      className="flex items-start gap-3 py-2.5"
                      style={{
                        borderBottom: '1px solid var(--color-border)',
                      }}
                    >
                      <span
                        className="flex-shrink-0 w-7 h-7 flex items-center justify-center text-xs"
                        style={{
                          fontFamily: 'var(--font-mono)',
                          color: 'var(--color-ink-4)',
                        }}
                      >
                        0{step}
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium leading-none mb-1.5" style={{ fontFamily: 'var(--font-ui)', color: 'var(--color-ink)' }}>
                          {title}
                        </p>
                        <p className="text-xs leading-snug" style={{ fontFamily: 'var(--font-body)', color: 'var(--color-ink-3)' }}>
                          {desc}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="hidden sm:block max-w-2xl w-full mb-8">
                <div
                  className="grid grid-cols-[0.78fr_1.22fr] w-full overflow-hidden"
                  style={{
                    minHeight: '208px',
                    borderRadius: '14px',
                    background: 'var(--color-elevated)',
                    border: '1px solid var(--color-border)',
                    boxShadow: '0 8px 24px rgba(26,25,22,0.06)',
                  }}
                >
                  <div
                    className="p-4 sm:p-5 flex flex-col justify-between"
                    style={{ background: 'var(--color-surface)', borderRight: '1px solid var(--color-border)' }}
                  >
                    <div>
                      <p className="text-xs font-medium mb-3" style={{ color: 'var(--color-ink-3)' }}>Source trail</p>
                      <div className="space-y-3">
                        <div className="flex items-start gap-2.5">
                          <span className="text-[11px] tabular-nums" style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent)' }}>01</span>
                          <span className="text-xs leading-snug" style={{ color: 'var(--color-ink-2)' }}>Original research</span>
                        </div>
                        <div className="flex items-start gap-2.5">
                          <span className="text-[11px] tabular-nums" style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent)' }}>02</span>
                          <span className="text-xs leading-snug" style={{ color: 'var(--color-ink-2)' }}>Technical documentation</span>
                        </div>
                      </div>
                    </div>
                    <span className="text-[11px]" style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-ink-4)' }}>Research notes</span>
                  </div>

                  <div
                    className="p-4 sm:p-5 flex flex-col justify-between"
                    style={{ background: '#252a35', color: '#f7f4ee' }}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[11px] font-medium" style={{ color: '#d8c8a9' }}>Lecture slide</span>
                      <span className="text-[11px] tabular-nums" style={{ fontFamily: 'var(--font-mono)', color: '#c4c6ca' }}>03 / 10</span>
                    </div>
                    <div className="py-4">
                      <p className="text-xl sm:text-2xl leading-tight" style={{ fontFamily: 'var(--font-display)', color: '#fffaf0' }}>
                        Keep evidence close to the claim
                      </p>
                      <div className="mt-3 h-px w-12" style={{ background: 'var(--color-accent-dim)' }} />
                    </div>
                    <div className="flex items-center justify-between gap-3 text-[11px]" style={{ color: '#c4c6ca' }}>
                      <span>Source-backed writing</span>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>[01] [02]</span>
                    </div>
                  </div>
                </div>
                <p className="mt-2 text-xs" style={{ color: 'var(--color-ink-4)' }}>
                  Research notes, carried into the lecture deck
                </p>
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
                borderRadius: '16px',
                boxShadow: '0 8px 24px rgba(26,25,22,0.06)',
              }}
            >
              {/* Form header */}
              <div
                className="px-6 py-5"
                style={{ borderBottom: '1px solid var(--color-border)' }}
              >
                <h2 className="text-lg font-medium" style={{ fontFamily: 'var(--font-ui)', color: 'var(--color-ink)' }}>
                  Article settings
                </h2>
              </div>
              {/* Form body */}
              <div className="px-5 py-6 sm:px-6">
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
