import { useState, useEffect, useRef } from 'react'
import { X, Mail, Lock, AlertCircle, CheckCircle2, ArrowRight } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

interface SignInModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function SignInModal({ isOpen, onClose }: SignInModalProps) {
  const { signInWithEmail, signUpWithEmail, signInWithGoogle } = useAuth()

  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [successNotice, setSuccessNotice] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const modalRef = useRef<HTMLDivElement>(null)

  // Reset state on open
  useEffect(() => {
    if (isOpen) {
      setError(null)
      setSuccessNotice(null)
      setEmail('')
      setPassword('')
    }
  }, [isOpen])

  // Close on Escape & trap focus
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccessNotice(null)
    setIsLoading(true)

    try {
      if (mode === 'signin') {
        const res = await signInWithEmail(email, password)
        if (res.error) {
          setError(res.error)
        } else {
          onClose()
        }
      } else {
        const res = await signUpWithEmail(email, password)
        if (res.error) {
          setError(res.error)
        } else if (res.needsConfirmation) {
          setSuccessNotice('Account created! Please check your email to confirm your account before signing in.')
        } else {
          onClose()
        }
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleGoogleSignIn = async () => {
    setError(null)
    setIsLoading(true)
    try {
      const res = await signInWithGoogle()
      if (res.error) {
        setError(res.error)
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs transition-opacity"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="signin-title"
        className="w-full max-w-md bg-[var(--color-elevated)] border border-[var(--color-border)] rounded-xl shadow-xl p-6 relative overflow-hidden transition-all"
        style={{
          background: 'var(--color-elevated)',
          borderColor: 'var(--color-border)',
        }}
      >
        {/* Close button */}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close dialog"
          className="absolute top-4 right-4 p-1.5 rounded-md text-[var(--color-ink-3)] hover:text-[var(--color-ink)] hover:bg-[var(--color-surface)] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Title */}
        <div className="mb-6">
          <h2
            id="signin-title"
            className="text-2xl font-normal tracking-tight"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--color-ink)', letterSpacing: '-0.015em' }}
          >
            {mode === 'signin' ? 'Sign in to SAGE' : 'Create a SAGE account'}
          </h2>
          <p className="text-xs mt-1 text-[var(--color-ink-3)]" style={{ fontFamily: 'var(--font-body)' }}>
            {mode === 'signin'
              ? 'Access your research history and saved BYOK models.'
              : 'Save generated articles, presentations, and custom API keys.'}
          </p>
        </div>

        {/* Google OAuth Button */}
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-2.5 h-10 px-4 rounded-lg text-sm font-medium border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-ink-2)] hover:bg-[var(--color-border-soft)] hover:text-[var(--color-ink)] transition-colors disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] mb-4"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          Continue with Google
        </button>

        <div className="flex items-center gap-3 my-4">
          <div className="flex-1 h-px bg-[var(--color-border)]" />
          <span className="text-[0.6875rem] font-medium text-[var(--color-ink-4)] uppercase tracking-wider">
            or with email
          </span>
          <div className="flex-1 h-px bg-[var(--color-border)]" />
        </div>

        {/* Error notification */}
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 p-3 mb-4 text-xs rounded-lg border border-[var(--color-error)]/20 bg-[var(--color-error-bg)] text-[var(--color-error)]"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Success confirmation notification */}
        {successNotice && (
          <div
            role="status"
            className="flex items-start gap-2 p-3 mb-4 text-xs rounded-lg border border-[var(--color-success)]/20 bg-[var(--color-success-bg)] text-[var(--color-success)]"
          >
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{successNotice}</span>
          </div>
        )}

        {/* Email & Password Form */}
        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div>
            <label
              htmlFor="signin-email"
              className="block text-xs font-semibold mb-1 text-[var(--color-ink-2)]"
            >
              Email address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-4)] pointer-events-none" />
              <input
                id="signin-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                disabled={isLoading}
                className="w-full h-10 pl-9 pr-3 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] placeholder-[var(--color-ink-4)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)] transition-all"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="signin-password"
              className="block text-xs font-semibold mb-1 text-[var(--color-ink-2)]"
            >
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-4)] pointer-events-none" />
              <input
                id="signin-password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                disabled={isLoading}
                className="w-full h-10 pl-9 pr-3 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] placeholder-[var(--color-ink-4)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)] transition-all"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 h-10 px-4 rounded-lg text-sm font-semibold text-[var(--color-ink-inv)] bg-[var(--color-accent)] hover:opacity-90 active:scale-[0.99] transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] mt-2"
          >
            {isLoading ? (
              <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                {mode === 'signin' ? 'Sign in' : 'Create account'}
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Footer toggles */}
        <div className="mt-5 pt-4 border-t border-[var(--color-border)] flex items-center justify-between text-xs text-[var(--color-ink-3)]">
          <button
            type="button"
            onClick={() => {
              setMode(mode === 'signin' ? 'signup' : 'signin')
              setError(null)
              setSuccessNotice(null)
            }}
            className="text-[var(--color-accent)] hover:underline font-medium focus:outline-none"
          >
            {mode === 'signin' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
          </button>

          <button
            type="button"
            onClick={onClose}
            className="text-[var(--color-ink-4)] hover:text-[var(--color-ink)] transition-colors focus:outline-none"
          >
            Continue as guest
          </button>
        </div>
      </div>
    </div>
  )
}
