import { ExternalLink, BookMarked, Calendar } from 'lucide-react'
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
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <BookMarked className="h-10 w-10 text-slate-600 mb-3" />
        <p className="text-slate-500 text-sm">
          No web sources were used for this blog post.
        </p>
        <p className="text-slate-600 text-xs mt-1">
          The content was generated from model knowledge (closed-book mode).
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-slate-400 text-sm">
        {sources.length} source{sources.length !== 1 ? 's' : ''} cited in this article
      </p>
      <div className="grid gap-3">
        {sources.map((source, i) => (
          <a
            key={i}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group block p-4 rounded-xl bg-white/[0.03] border border-white/8 hover:bg-white/[0.06] hover:border-purple-500/30 transition-all duration-200"
          >
            <div className="flex items-start gap-3">
              {/* Favicon */}
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center overflow-hidden mt-0.5">
                <img
                  src={getFaviconUrl(source.url)}
                  alt=""
                  className="w-5 h-5"
                  onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-slate-200 text-sm font-medium leading-snug group-hover:text-white transition-colors line-clamp-2">
                    {source.title || getDomain(source.url)}
                  </p>
                  <ExternalLink className="flex-shrink-0 h-3.5 w-3.5 text-slate-500 group-hover:text-purple-400 transition-colors mt-0.5" />
                </div>

                <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                  <span className="text-xs text-slate-500">{getDomain(source.url)}</span>
                  {source.published_at && (
                    <span className="flex items-center gap-1 text-xs text-slate-600">
                      <Calendar className="h-3 w-3" />
                      {source.published_at}
                    </span>
                  )}
                </div>

                {source.snippet && (
                  <p className="text-xs text-slate-500 mt-2 leading-relaxed line-clamp-2">
                    {source.snippet}
                  </p>
                )}
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
