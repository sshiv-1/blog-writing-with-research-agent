import { useState, useEffect, useRef } from 'react'
import {
  X,
  Key,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  Trash2,
  RefreshCw,
  Sparkles,
  Layers,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useModelSettings, PROVIDERS } from '@/context/ModelSettingsContext'
import { testLlmConnection } from '@/api/client'

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { user } = useAuth()
  const {
    provider,
    setProvider,
    model,
    setModel,
    customModel,
    setCustomModel,
    slidesProvider,
    setSlidesProvider,
    slidesModel,
    setSlidesModel,
    customSlidesModel,
    setCustomSlidesModel,
    effectiveArticleModel,
    effectiveSlidesProvider,
    savedKeys,
    saveKey,
    removeKey,
    getGuestKey,
  } = useModelSettings()

  const [inputKey, setInputKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [isReplacingKey, setIsReplacingKey] = useState(false)
  const [keyActionMsg, setKeyActionMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const modalRef = useRef<HTMLDivElement>(null)

  // Reset transient input states on open or provider change
  useEffect(() => {
    if (isOpen) {
      setInputKey('')
      setShowKey(false)
      setIsReplacingKey(false)
      setKeyActionMsg(null)
      setTestResult(null)
    }
  }, [isOpen, provider])

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const activeProviderConfig = PROVIDERS[provider]
  const currentSavedKey = user ? savedKeys.find((k) => k.provider === provider) : null
  const currentGuestKey = !user ? getGuestKey(provider) : null

  // Has existing key configured
  const hasExistingKey = Boolean(currentSavedKey || currentGuestKey)
  const existingKeyLast4 = currentSavedKey?.last4 || (currentGuestKey ? currentGuestKey.slice(-4) : '')

  const handleSaveKey = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputKey.trim()) return

    setKeyActionMsg(null)
    const res = await saveKey(provider, inputKey.trim())
    if (res.ok) {
      setKeyActionMsg({
        type: 'success',
        text: user ? 'API key saved securely to your account.' : 'API key saved for this tab session.',
      })
      setInputKey('')
      setIsReplacingKey(false)
    } else {
      setKeyActionMsg({
        type: 'error',
        text: res.error || 'Failed to save API key.',
      })
    }
  }

  const handleRemoveKey = async () => {
    setKeyActionMsg(null)
    const res = await removeKey(provider)
    if (res.ok) {
      setKeyActionMsg({ type: 'success', text: 'API key removed.' })
      setIsReplacingKey(false)
    } else {
      setKeyActionMsg({ type: 'error', text: res.error || 'Failed to remove API key.' })
    }
  }

  const handleTestConnection = async () => {
    setIsTesting(true)
    setTestResult(null)

    // Build headers matching what routes.py expects
    const headers: Record<string, string> = {
      'X-LLM-Provider': provider,
      'X-LLM-Model': effectiveArticleModel,
    }

    // Determine key to test
    const keyToSend = inputKey.trim() || currentGuestKey || ''
    if (keyToSend) {
      headers['X-LLM-Key'] = keyToSend
    }

    try {
      const res = await testLlmConnection(headers)
      if (res.ok) {
        setTestResult({
          ok: true,
          message: `Connected successfully to ${res.provider} (${res.model}).`,
        })
      } else {
        setTestResult({
          ok: false,
          message: res.error || 'Connection probe failed.',
        })
      }
    } catch (err: any) {
      setTestResult({
        ok: false,
        message: err.message || 'Failed to test model connectivity.',
      })
    } finally {
      setIsTesting(false)
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
        aria-labelledby="settings-title"
        className="w-full max-w-xl max-h-[90vh] flex flex-col bg-[var(--color-elevated)] border border-[var(--color-border)] rounded-xl shadow-xl overflow-hidden transition-all"
        style={{
          background: 'var(--color-elevated)',
          borderColor: 'var(--color-border)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-[var(--color-accent)]" />
            <h2
              id="settings-title"
              className="text-lg font-normal tracking-tight text-[var(--color-ink)]"
              style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.01em' }}
            >
              Model & BYOK Settings
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1.5 rounded-md text-[var(--color-ink-3)] hover:text-[var(--color-ink)] hover:bg-[var(--color-border-soft)] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable content body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {/* 1. Article Model Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[var(--color-ink-3)]" />
              <h3 className="text-sm font-semibold text-[var(--color-ink)] tracking-tight">
                Article Generation Model
              </h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Provider dropdown */}
              <div>
                <label
                  htmlFor="model-provider"
                  className="block text-xs font-semibold mb-1 text-[var(--color-ink-2)]"
                >
                  Provider
                </label>
                <select
                  id="model-provider"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full h-9 px-3 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]"
                >
                  {Object.values(PROVIDERS).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Model selection */}
              <div>
                <label
                  htmlFor="model-select"
                  className="block text-xs font-semibold mb-1 text-[var(--color-ink-2)]"
                >
                  Model
                </label>
                {activeProviderConfig?.isCustomOnly ? (
                  <div>
                    <input
                      id="model-select"
                      type="text"
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                      placeholder="e.g. gemini-2.5-pro or anthropic/claude-3.5-sonnet"
                      className="w-full h-9 px-3 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] placeholder-[var(--color-ink-4)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]"
                    />
                    <p className="text-[0.6875rem] text-[var(--color-ink-3)] mt-1">
                      Enter a model ID from the provider&apos;s docs.
                    </p>
                  </div>
                ) : (
                  <div>
                    <select
                      id="model-select"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      className="w-full h-9 px-3 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]"
                    >
                      {activeProviderConfig.recommendedModels.map((m) => (
                        <option key={m} value={m}>
                          {m} {m === activeProviderConfig.defaultModel ? '(Default)' : ''}
                        </option>
                      ))}
                      <option value="custom">Custom model ID...</option>
                    </select>

                    {model === 'custom' && (
                      <input
                        type="text"
                        value={customModel}
                        onChange={(e) => setCustomModel(e.target.value)}
                        placeholder="Enter custom model identifier"
                        className="w-full h-9 px-3 mt-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] placeholder-[var(--color-ink-4)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]"
                      />
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="h-px bg-[var(--color-border)]" />

          {/* 2. Slides Model Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-[var(--color-ink-3)]" />
                <h3 className="text-sm font-semibold text-[var(--color-ink)] tracking-tight">
                  Presentation Deck Model
                </h3>
              </div>
            </div>
            <p className="text-xs text-[var(--color-ink-3)]">
              The slides model affects depth the most. You can use the same model or configure a frontier reasoning model for slides.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="slides-provider"
                  className="block text-xs font-semibold mb-1 text-[var(--color-ink-2)]"
                >
                  Slides Provider
                </label>
                <select
                  id="slides-provider"
                  value={slidesProvider}
                  onChange={(e) => setSlidesProvider(e.target.value)}
                  className="w-full h-9 px-3 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]"
                >
                  <option value="same">Same as article model</option>
                  {Object.values(PROVIDERS).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              {slidesProvider !== 'same' && (
                <div>
                  <label
                    htmlFor="slides-model"
                    className="block text-xs font-semibold mb-1 text-[var(--color-ink-2)]"
                  >
                    Slides Model
                  </label>
                  {PROVIDERS[effectiveSlidesProvider]?.isCustomOnly ? (
                    <div>
                      <input
                        id="slides-model"
                        type="text"
                        value={customSlidesModel}
                        onChange={(e) => setCustomSlidesModel(e.target.value)}
                        placeholder="Enter model ID from provider docs"
                        className="w-full h-9 px-3 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] placeholder-[var(--color-ink-4)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]"
                      />
                      <p className="text-[0.6875rem] text-[var(--color-ink-3)] mt-1">
                        Enter a model ID from the provider&apos;s docs.
                      </p>
                    </div>
                  ) : (
                    <div>
                      <select
                        id="slides-model"
                        value={slidesModel}
                        onChange={(e) => setSlidesModel(e.target.value)}
                        className="w-full h-9 px-3 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]"
                      >
                        <option value="same">Default for {PROVIDERS[effectiveSlidesProvider]?.name}</option>
                        {PROVIDERS[effectiveSlidesProvider]?.recommendedModels.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                        <option value="custom">Custom model ID...</option>
                      </select>

                      {slidesModel === 'custom' && (
                        <input
                          type="text"
                          value={customSlidesModel}
                          onChange={(e) => setCustomSlidesModel(e.target.value)}
                          placeholder="Enter custom slide model ID"
                          className="w-full h-9 px-3 mt-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] placeholder-[var(--color-ink-4)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]"
                        />
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="h-px bg-[var(--color-border)]" />

          {/* 3. API Key & BYOK Storage */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Key className="w-4 h-4 text-[var(--color-ink-3)]" />
              <h3 className="text-sm font-semibold text-[var(--color-ink)] tracking-tight">
                API Key for {activeProviderConfig.name}
              </h3>
            </div>

            {/* Note about storage scope */}
            <p className="text-xs text-[var(--color-ink-3)] leading-relaxed">
              {user ? (
                <>
                  Keys are symmetrically encrypted with Fernet and saved to your account. Full keys are never exposed back to the client.
                </>
              ) : (
                <>
                  Kept in this browser tab only. Sent with your requests, never stored on our servers.
                </>
              )}
            </p>

            {/* Key Action notice */}
            {keyActionMsg && (
              <div
                role="status"
                className={`flex items-start gap-2 p-3 text-xs rounded-lg border ${
                  keyActionMsg.type === 'success'
                    ? 'border-[var(--color-success)]/20 bg-[var(--color-success-bg)] text-[var(--color-success)]'
                    : 'border-[var(--color-error)]/20 bg-[var(--color-error-bg)] text-[var(--color-error)]'
                }`}
              >
                {keyActionMsg.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                )}
                <span>{keyActionMsg.text}</span>
              </div>
            )}

            {/* If key already saved & not replacing */}
            {hasExistingKey && !isReplacingKey ? (
              <div className="flex items-center justify-between p-3.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-[var(--color-success)]" />
                  <span className="text-xs font-mono font-medium text-[var(--color-ink)]">
                    •••• {existingKeyLast4}
                  </span>
                  <span className="text-[0.6875rem] px-1.5 py-0.5 rounded bg-[var(--color-success-bg)] text-[var(--color-success)] font-semibold">
                    {user ? 'Account Saved' : 'Session Tab'}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setIsReplacingKey(true)}
                    className="text-xs font-medium text-[var(--color-accent)] hover:underline focus:outline-none"
                  >
                    Replace
                  </button>
                  <span className="text-[var(--color-border-strong)]">·</span>
                  <button
                    type="button"
                    onClick={handleRemoveKey}
                    aria-label="Remove saved key"
                    className="text-xs font-medium text-[var(--color-error)] hover:underline flex items-center gap-1 focus:outline-none"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Remove
                  </button>
                </div>
              </div>
            ) : (
              /* Input form for saving key */
              <form onSubmit={handleSaveKey} className="space-y-3">
                <div className="relative">
                  <input
                    type={showKey ? 'text' : 'password'}
                    autoComplete="off"
                    value={inputKey}
                    onChange={(e) => setInputKey(e.target.value)}
                    placeholder={provider === 'groq' ? 'Optional for Groq (gsk_...)' : `Enter ${activeProviderConfig.name} API key`}
                    className="w-full h-10 pl-3 pr-10 text-sm font-mono rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] text-[var(--color-ink)] placeholder-[var(--color-ink-4)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    aria-label={showKey ? 'Hide key' : 'Show key'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-4)] hover:text-[var(--color-ink)] transition-colors focus:outline-none"
                  >
                    {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                <div className="flex items-center gap-2 justify-end">
                  {hasExistingKey && (
                    <button
                      type="button"
                      onClick={() => setIsReplacingKey(false)}
                      className="h-8 px-3 text-xs font-medium text-[var(--color-ink-3)] hover:text-[var(--color-ink)] focus:outline-none"
                    >
                      Cancel
                    </button>
                  )}
                  <button
                    type="submit"
                    disabled={!inputKey.trim()}
                    className="h-8 px-3.5 text-xs font-semibold rounded-lg bg-[var(--color-accent)] text-[var(--color-ink-inv)] hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] cursor-pointer"
                  >
                    {user ? 'Save key to my account' : 'Use key for this session'}
                  </button>
                </div>
              </form>
            )}
          </div>

          <div className="h-px bg-[var(--color-border)]" />

          {/* 4. Test Connection Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-semibold text-[var(--color-ink)]">
                  Verify Model Connectivity
                </h4>
                <p className="text-[0.6875rem] text-[var(--color-ink-3)]">
                  Runs a ~16-token probe against {activeProviderConfig.name}.
                </p>
              </div>

              <button
                type="button"
                onClick={handleTestConnection}
                disabled={isTesting}
                className="flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-ink)] hover:bg-[var(--color-border-soft)] disabled:opacity-50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin' : ''}`} />
                {isTesting ? 'Testing...' : 'Test connection'}
              </button>
            </div>

            {testResult && (
              <div
                role="status"
                className={`flex items-start gap-2 p-3 text-xs rounded-lg border ${
                  testResult.ok
                    ? 'border-[var(--color-success)]/20 bg-[var(--color-success-bg)] text-[var(--color-success)]'
                    : 'border-[var(--color-error)]/20 bg-[var(--color-error-bg)] text-[var(--color-error)]'
                }`}
              >
                {testResult.ok ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                )}
                <span className="font-mono text-[0.6875rem] leading-relaxed break-words">{testResult.message}</span>
              </div>
            )}
          </div>

        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-[var(--color-border)] bg-[var(--color-surface)] flex items-center justify-end">
          <button
            type="button"
            onClick={onClose}
            className="h-9 px-4 text-xs font-semibold rounded-lg bg-[var(--color-ink)] text-[var(--color-canvas)] hover:opacity-90 active:scale-[0.99] transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
