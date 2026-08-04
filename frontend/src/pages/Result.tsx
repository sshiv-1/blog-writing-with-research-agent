import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, AlertCircle, BookMarked, BookText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useJobStatus } from '@/hooks/useJobStatus'
import ProgressStepper from '@/components/ProgressStepper'
import OutputEditor from '@/components/OutputEditor'
import SourceList from '@/components/SourceList'

export default function Result() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const { status, result, isLoading, error } = useJobStatus(jobId ?? null)

  const isDone = status?.status === 'done' && result !== null

  return (
    <div className="min-h-screen bg-[#09090b] relative overflow-hidden">
      {/* Ambient glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 70% 40% at 50% -5%, rgba(124,58,237,0.14) 0%, transparent 55%)',
        }}
      />

      <div className="relative z-10 max-w-4xl mx-auto px-4 py-10">
        {/* Top nav */}
        <div className="flex items-center gap-4 mb-10">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/')}
            className="text-slate-400 hover:text-white hover:bg-white/5 gap-2 rounded-lg"
          >
            <ArrowLeft className="h-4 w-4" />
            New blog
          </Button>

          {isDone && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-emerald-300 text-xs font-medium">Generated</span>
            </div>
          )}
        </div>

        {/* ── LOADING / PROGRESS VIEW ── */}
        {isLoading && !isDone && (
          <div className="flex flex-col items-center justify-center gap-8 py-8">
            <div className="text-center">
              <h1 className="text-2xl font-bold text-white mb-2">Generating your blog…</h1>
              <p className="text-slate-400 text-sm">
                This takes 30–90 seconds. Sit back and watch the agent work.
              </p>
            </div>

            <div
              className="w-full max-w-md rounded-2xl border border-white/8 p-8"
              style={{
                background: 'linear-gradient(135deg, rgba(26,26,40,0.9), rgba(17,17,24,0.95))',
                backdropFilter: 'blur(20px)',
                boxShadow: '0 0 0 1px rgba(124,58,237,0.1), 0 25px 50px rgba(0,0,0,0.5)',
              }}
            >
              <ProgressStepper jobStatus={status} />
            </div>
          </div>
        )}

        {/* ── ERROR VIEW ── */}
        {error && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-4">
              <AlertCircle className="h-8 w-8 text-red-400" />
            </div>
            <h2 className="text-xl font-bold text-white mb-2">Generation failed</h2>
            <p className="text-slate-400 text-sm max-w-md mb-6">{error}</p>
            <Button
              onClick={() => navigate('/')}
              className="bg-purple-600 hover:bg-purple-500 text-white rounded-xl"
            >
              Try again
            </Button>
          </div>
        )}

        {/* ── RESULT VIEW ── */}
        {isDone && result && (
          <div className="space-y-8">
            {/* Title */}
            <div>
              <p className="text-purple-400 text-sm font-medium mb-2 uppercase tracking-wider">
                Generated Article
              </p>
              <h1 className="text-3xl sm:text-4xl font-bold text-white leading-tight">
                {result.title}
              </h1>
            </div>

            {/* Main content tabs */}
            <Tabs defaultValue="article" className="w-full">
              <TabsList className="bg-white/5 border border-white/10 rounded-xl p-1 gap-1 mb-6">
                <TabsTrigger
                  value="article"
                  className="rounded-lg data-[state=active]:bg-purple-600 data-[state=active]:text-white text-slate-400 gap-2"
                >
                  <BookText className="h-4 w-4" />
                  Article
                </TabsTrigger>
                <TabsTrigger
                  value="sources"
                  className="rounded-lg data-[state=active]:bg-purple-600 data-[state=active]:text-white text-slate-400 gap-2"
                >
                  <BookMarked className="h-4 w-4" />
                  Sources
                  {result.sources.length > 0 && (
                    <span className="ml-1 text-xs bg-purple-500/30 text-purple-300 px-1.5 py-0.5 rounded-full">
                      {result.sources.length}
                    </span>
                  )}
                </TabsTrigger>
              </TabsList>

              <TabsContent value="article">
                <div
                  className="rounded-2xl border border-white/8 p-6 sm:p-8"
                  style={{
                    background: 'linear-gradient(135deg, rgba(26,26,40,0.8), rgba(17,17,24,0.9))',
                    backdropFilter: 'blur(20px)',
                  }}
                >
                  <OutputEditor result={result} />
                </div>
              </TabsContent>

              <TabsContent value="sources">
                <div
                  className="rounded-2xl border border-white/8 p-6 sm:p-8"
                  style={{
                    background: 'linear-gradient(135deg, rgba(26,26,40,0.8), rgba(17,17,24,0.9))',
                    backdropFilter: 'blur(20px)',
                  }}
                >
                  <SourceList sources={result.sources} />
                </div>
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>
    </div>
  )
}
