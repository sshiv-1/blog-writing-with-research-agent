import { ExternalLink, Library, Calendar } from 'lucide-react'
import type { Source } from '@/api/client'

interface Props {
  sources: Source[]
}

function getDomain(url: string): string {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return url
  }
}

function getFaviconUrl(url: string): string {
  try {
    const { origin } = new URL(url)
    return `https://www.google.com/s2/favicons?domain=${origin}&sz=32`
  } catch {
    return ''
  }
}

export default function SourceList({ sources }: Props) {
  if (sources.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Library
          className="h-8 w-8 mb-3"
          style={{ color: 'var(--color-border-strong)' }}
          strokeWidth={1.5}
        />
        <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-ink-3)' }}>
          No web sources used
        </p>
        <p className="text-xs max-w-[30ch]" style={{ color: 'var(--color-ink-4)' }}>
          This article was generated from model knowledge (closed-book mode).
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-baseline gap-2">
        <p className="text-sm font-semibold" style={{ color: 'var(--color-ink)' }}>
          {sources.length} {sources.length === 1 ? 'source' : 'sources'} cited
        </p>
        <span className="text-xs" style={{ color: 'var(--color-ink-4)' }}>
          in this article
        </span>
      </div>

      {/* Source list */}
      <div className="space-y-2">
        {sources.map((source, i) => (
          <a
            key={i}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-start gap-3 px-4 py-3.5 transition-colors"
            style={{
              borderRadius: '4px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              textDecoration: 'none',
            }}
          >
            {/* Citation number */}
            <span
              className="flex-shrink-0 w-5 h-5 flex items-center justify-center text-[10px] font-semibold mt-0.5"
              style={{
                borderRadius: '3px',
                background: 'var(--color-border)',
                color: 'var(--color-ink-4)',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {i + 1}
            </span>

            {/* Favicon */}
            <div
              className="flex-shrink-0 w-5 h-5 flex items-center justify-center overflow-hidden mt-0.5"
              style={{ borderRadius: '3px', background: 'var(--color-border)' }}
            >
              <img
                src={getFaviconUrl(source.url)}
                alt=""
                className="w-4 h-4"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <p
                  className="text-sm font-medium leading-snug line-clamp-2 transition-colors"
                  style={{
                    color: 'var(--color-ink)',
                  }}
                >
                  {source.title || getDomain(source.url)}
                </p>
                <ExternalLink
                  className="flex-shrink-0 h-3.5 w-3.5 mt-0.5 transition-colors"
                  style={{ color: 'var(--color-ink-4)' }}
                  strokeWidth={1.5}
                />
              </div>

              <div className="flex items-center gap-3 mt-1 flex-wrap">
                <span className="text-xs" style={{ color: 'var(--color-ink-4)' }}>
                  {getDomain(source.url)}
                </span>
                {source.published_at && (
                  <span
                    className="flex items-center gap-1 text-xs"
                    style={{ color: 'var(--color-ink-4)' }}
                  >
                    <Calendar className="h-2.5 w-2.5" strokeWidth={1.5} />
                    {source.published_at}
                  </span>
                )}
              </div>

              {source.snippet && (
                <p
                  className="text-xs mt-1.5 leading-relaxed line-clamp-2"
                  style={{ color: 'var(--color-ink-3)' }}
                >
                  {source.snippet}
                </p>
              )}
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
