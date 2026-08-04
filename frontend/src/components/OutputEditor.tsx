import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, Download, Check, Edit3, Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import type { BlogResult } from '@/api/client'

interface Props {
  result: BlogResult
}

export default function OutputEditor({ result }: Props) {
  const [editedDraft, setEditedDraft] = useState(result.draft)
  const [copied, setCopied] = useState(false)

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
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="border-purple-500/40 text-purple-300 text-xs">
            ~{wordCount.toLocaleString()} words
          </Badge>
          <Badge variant="outline" className="border-emerald-500/40 text-emerald-300 text-xs">
            {result.sources.length} sources
          </Badge>
          <Badge variant="outline" className="border-cyan-500/40 text-cyan-300 text-xs">
            {result.outline.length} sections
          </Badge>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            className="border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white gap-2 rounded-lg"
          >
            {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
            {copied ? 'Copied!' : 'Copy'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownload}
            className="border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white gap-2 rounded-lg"
          >
            <Download className="h-4 w-4" />
            .md
          </Button>
        </div>
      </div>

      {/* Tabs: Preview / Edit / Outline */}
      <Tabs defaultValue="preview" className="w-full">
        <TabsList className="bg-white/5 border border-white/10 rounded-xl p-1 gap-1">
          <TabsTrigger
            value="preview"
            className="rounded-lg data-[state=active]:bg-purple-600 data-[state=active]:text-white text-slate-400 gap-2"
          >
            <Eye className="h-4 w-4" />
            Preview
          </TabsTrigger>
          <TabsTrigger
            value="edit"
            className="rounded-lg data-[state=active]:bg-purple-600 data-[state=active]:text-white text-slate-400 gap-2"
          >
            <Edit3 className="h-4 w-4" />
            Edit
          </TabsTrigger>
        </TabsList>

        {/* Preview tab */}
        <TabsContent value="preview" className="mt-4">
          <div className="prose prose-invert prose-slate max-w-none
            prose-headings:font-bold prose-headings:text-white
            prose-h1:text-3xl prose-h1:text-purple-200
            prose-h2:text-xl prose-h2:text-slate-200 prose-h2:border-b prose-h2:border-white/10 prose-h2:pb-2
            prose-p:text-slate-300 prose-p:leading-relaxed
            prose-a:text-purple-400 prose-a:no-underline hover:prose-a:underline
            prose-strong:text-white
            prose-code:text-cyan-300 prose-code:bg-cyan-950/40 prose-code:rounded prose-code:px-1.5 prose-code:py-0.5 prose-code:text-sm prose-code:before:content-none prose-code:after:content-none
            prose-pre:bg-[#0d0d18] prose-pre:border prose-pre:border-white/10 prose-pre:rounded-xl
            prose-blockquote:border-l-purple-500 prose-blockquote:text-slate-400
            prose-ul:text-slate-300 prose-li:marker:text-purple-400
            prose-ol:text-slate-300">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {editedDraft}
            </ReactMarkdown>
          </div>
        </TabsContent>

        {/* Edit tab */}
        <TabsContent value="edit" className="mt-4">
          <textarea
            value={editedDraft}
            onChange={e => setEditedDraft(e.target.value)}
            className="w-full min-h-[600px] p-4 rounded-xl bg-[#0d0d18] border border-white/10 text-slate-200 font-mono text-sm leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500/50"
            spellCheck={false}
          />
          <p className="text-xs text-slate-500 mt-2">
            Edit the Markdown directly. Switch to Preview to see rendered output.
          </p>
        </TabsContent>
      </Tabs>
    </div>
  )
}
