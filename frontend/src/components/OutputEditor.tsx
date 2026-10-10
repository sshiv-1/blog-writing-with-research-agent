import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, Download, Check, Edit3, Eye } from 'lucide-react'
import type { BlogResult } from '@/api/client'

interface Props {
  result: BlogResult
}

type Tab = 'preview' | 'edit'

export default function OutputEditor({ result }: Props) {
  const [editedDraft, setEditedDraft] = useState(result.draft)
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<Tab>('preview')

  const handleCopy = async () => {
    await navigator.clipboard.writeText(editedDraft)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const slug = result.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .slice(0, 60)
    const blob = new Blob([editedDraft], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${slug}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const wordCount = editedDraft.split(/\s+/).filter(Boolean).length

  return (
    <div className="space-y-0">
      {/* Toolbar */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{
          borderRadius: '6px 6px 0 0',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderBottom: '1px solid var(--color-border-soft)',
        }}
      >
        {/* Tab switcher */}
        <div
          className="flex items-center gap-0.5 p-0.5"
          style={{
            borderRadius: '4px',
            background: 'var(--color-border)',
          }}
        >
          {([
            { id: 'preview' as Tab, icon: Eye, label: 'Preview' },
            { id: 'edit' as Tab, icon: Edit3, label: 'Edit' },
          ] as const).map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-all"
              style={{
                borderRadius: '3px',
                background: activeTab === id ? 'var(--color-elevated)' : 'transparent',
                color: activeTab === id ? 'var(--color-ink)' : 'var(--color-ink-4)',
                boxShadow: activeTab === id ? '0 1px 2px rgba(26,25,22,0.06)' : 'none',
              }}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Metadata + actions */}
        <div className="flex items-center gap-3">
          {/* Metadata */}
          <div className="hidden sm:flex items-center gap-3 text-xs" style={{ color: 'var(--color-ink-4)' }}>
            <span>~{wordCount.toLocaleString()} words</span>
            <span
              className="w-0.5 h-3"
              style={{ background: 'var(--color-border-strong)', borderRadius: '1px' }}
              aria-hidden
            />
            <span>{result.sources.length} sources</span>
            <span
              className="w-0.5 h-3"
              style={{ background: 'var(--color-border-strong)', borderRadius: '1px' }}
              aria-hidden
            />
            <span>{result.outline.length} sections</span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-1.5 h-7 px-2.5 text-xs font-medium transition-colors"
              style={{
                borderRadius: '4px',
                background: 'var(--color-elevated)',
                border: '1px solid var(--color-border)',
                color: copied ? 'var(--color-success)' : 'var(--color-ink-2)',
              }}
            >
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            <button
              type="button"
              onClick={handleDownload}
              className="flex items-center gap-1.5 h-7 px-2.5 text-xs font-medium transition-colors"
              style={{
                borderRadius: '4px',
                background: 'var(--color-elevated)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-ink-2)',
              }}
            >
              <Download className="h-3.5 w-3.5" />
              .md
            </button>
          </div>
        </div>
      </div>

      {/* Content panel */}
      <div
        className="overflow-hidden"
        style={{
          borderRadius: '0 0 6px 6px',
          border: '1px solid var(--color-border)',
          borderTop: 'none',
          background: 'var(--color-elevated)',
        }}
      >
        {activeTab === 'preview' ? (
          <div className="px-6 py-8 sm:px-10 sm:py-10">
            <div className="article-prose max-w-[70ch]">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {editedDraft}
              </ReactMarkdown>
            </div>
          </div>
        ) : (
          <div className="p-4">
            <textarea
              value={editedDraft}
              onChange={e => setEditedDraft(e.target.value)}
              className="w-full min-h-[600px] p-4 text-sm leading-relaxed resize-y"
              style={{
                borderRadius: '4px',
                fontFamily: 'var(--font-mono)',
                background: 'var(--color-canvas)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-ink-2)',
                fontSize: '0.8125rem',
              }}
              spellCheck={false}
              placeholder="Edit the Markdown directly…"
            />
            <p className="text-xs mt-2" style={{ color: 'var(--color-ink-4)' }}>
              Edit Markdown directly. Switch to Preview to see rendered output.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
