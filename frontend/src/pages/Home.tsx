import BlogForm from '@/components/BlogForm'

export default function Home() {
  return (
    <div
      className="min-h-[100dvh] flex flex-col"
      style={{ background: 'var(--color-canvas)' }}
    >
      {/* Top bar — full width with inner max-width alignment */}
      <header
        className="sticky top-0 z-40 flex items-center h-14 px-6"
        style={{
          background: 'var(--color-overlay)',
          borderBottom: '1px solid var(--color-border)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
        }}
      >
        <div className="w-full max-w-6xl mx-auto flex items-center gap-2">
          <span
            className="text-sm font-semibold"
            style={{ color: 'var(--color-ink)', letterSpacing: '-0.02em' }}
          >
            odis
          </span>
          <span
            className="text-xs px-1.5 py-0.5"
            style={{
              background: 'var(--color-accent-muted)',
              color: 'var(--color-accent)',
              fontSize: '0.6875rem',
              fontWeight: 600,
              borderRadius: '3px',
            }}
          >
            BETA
          </span>
        </div>
      </header>

      {/* Main — split layout at lg, stacked on mobile */}
      <main className="flex-1 flex items-start justify-center px-6 py-12 sm:py-16">
        <div className="w-full max-w-6xl">
          {/* Grid: 5/7 left copy, 4/7 right form on desktop */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_440px] gap-12 lg:gap-16 items-start">

            {/* ── Left: intro copy ── */}
            <div className="pt-2 lg:pt-4">
              <h1
                className="text-[2.375rem] sm:text-[3rem] lg:text-[3.25rem] font-bold leading-[1.08] mb-5"
                style={{ color: 'var(--color-ink)', letterSpacing: '-0.038em' }}
              >
                Write research-backed articles
                <span
                  style={{
                    display: 'block',
                    color: 'var(--color-ink-3)',
                    fontWeight: 400,
                    marginTop: '0.1em',
                  }}
                >
                  in minutes.
                </span>
              </h1>

              <p
                className="text-base leading-relaxed mb-8 max-w-[46ch]"
                style={{ color: 'var(--color-ink-3)', fontSize: '1.0625rem' }}
              >
                Provide a topic and your preferences. The agent researches the web,
                builds an outline, drafts every section in parallel, and delivers
                a cited, publication-ready article.
              </p>

              {/* Capability chips — restrained geometry */}
              <div className="flex flex-wrap gap-2 mb-10 lg:mb-0">
                {[
                  { label: 'Live web research', detail: 'Tavily' },
                  { label: 'Parallel section drafting', detail: 'LangGraph' },
                  { label: 'Cited sources', detail: 'Every claim' },
                ].map(({ label, detail }) => (
                  <span
                    key={label}
                    className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1"
                    style={{
                      background: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                      color: 'var(--color-ink-3)',
                      borderRadius: '4px',
                    }}
                  >
                    {label}
                    <span style={{ color: 'var(--color-ink-4)', fontWeight: 400 }}>· {detail}</span>
                  </span>
                ))}
              </div>

              {/* Footer note — visible only on desktop left col */}
              <p
                className="text-xs hidden lg:block"
                style={{ color: 'var(--color-ink-4)', marginTop: '2.5rem' }}
              >
                Powered by LangGraph + Gemini · Tavily web search
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
                  className="text-xs font-semibold uppercase"
                  style={{
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

          </div>
        </div>
      </main>

      {/* Mobile footer */}
      <p
        className="text-xs text-center pb-6 lg:hidden"
        style={{ color: 'var(--color-ink-4)' }}
      >
        Powered by LangGraph + Gemini · Tavily web search
      </p>
    </div>
  )
}
