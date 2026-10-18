import { createContext, useContext, useEffect, useState, type ReactNode, useCallback } from 'react'
import { useAuth } from './AuthContext'
import { getUserSavedKeys, saveUserKey as apiSaveUserKey, deleteUserKey as apiDeleteUserKey, type UserKeyItem } from '@/api/client'

export interface ProviderConfig {
  id: string
  name: string
  defaultModel: string
  recommendedModels: string[]
  isCustomOnly?: boolean
}

export const PROVIDERS: Record<string, ProviderConfig> = {
  groq: {
    id: 'groq',
    name: 'Groq (Free default)',
    defaultModel: 'openai/gpt-oss-120b',
    recommendedModels: ['openai/gpt-oss-120b', 'llama-3.3-70b-versatile'],
  },
  openai: {
    id: 'openai',
    name: 'OpenAI',
    defaultModel: 'gpt-6.1-sol',
    recommendedModels: ['gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna'],
  },
  anthropic: {
    id: 'anthropic',
    name: 'Anthropic',
    defaultModel: 'claude-sonnet-5-5',
    recommendedModels: ['claude-sonnet-5-5', 'claude-haiku-5-5', 'claude-opus-5-5'],
  },
  google: {
    id: 'google',
    name: 'Google Gemini',
    defaultModel: '',
    recommendedModels: [],
    isCustomOnly: true,
  },
  openrouter: {
    id: 'openrouter',
    name: 'OpenRouter',
    defaultModel: '',
    recommendedModels: [],
    isCustomOnly: true,
  },
}

interface ModelSettingsContextType {
  provider: string
  setProvider: (p: string) => void
  model: string
  setModel: (m: string) => void
  customModel: string
  setCustomModel: (cm: string) => void
  slidesProvider: string
  setSlidesProvider: (sp: string) => void
  slidesModel: string
  setSlidesModel: (sm: string) => void
  customSlidesModel: string
  setCustomSlidesModel: (csm: string) => void

  effectiveArticleModel: string
  effectiveSlidesProvider: string
  effectiveSlidesModel: string

  savedKeys: UserKeyItem[]
  refreshSavedKeys: () => Promise<void>
  saveKey: (provider: string, apiKey: string) => Promise<{ ok: boolean; error?: string; last4?: string }>
  removeKey: (provider: string) => Promise<{ ok: boolean; error?: string }>

  getGuestKey: (provider: string) => string | null
  setGuestKey: (provider: string, key: string) => void
  removeGuestKey: (provider: string) => void

  hasKeyForProvider: (provider: string) => boolean
  headerLabel: string
  isSettingsOpen: boolean
  setIsSettingsOpen: (open: boolean) => void
  isSignInOpen: boolean
  setIsSignInOpen: (open: boolean) => void
}

const ModelSettingsContext = createContext<ModelSettingsContextType | null>(null)

export function ModelSettingsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()

  // Non-secret settings in localStorage
  const [provider, setProviderState] = useState<string>(() => localStorage.getItem('sage_pref_provider') || 'groq')
  const [model, setModelState] = useState<string>(() => localStorage.getItem('sage_pref_model') || 'openai/gpt-oss-120b')
  const [customModel, setCustomModelState] = useState<string>(() => localStorage.getItem('sage_pref_custom_model') || '')
  const [slidesProvider, setSlidesProviderState] = useState<string>(() => localStorage.getItem('sage_pref_slides_provider') || 'same')
  const [slidesModel, setSlidesModelState] = useState<string>(() => localStorage.getItem('sage_pref_slides_model') || 'same')
  const [customSlidesModel, setCustomSlidesModelState] = useState<string>(() => localStorage.getItem('sage_pref_custom_slides_model') || '')

  const [savedKeys, setSavedKeys] = useState<UserKeyItem[]>([])
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isSignInOpen, setIsSignInOpen] = useState(false)

  // Sync preference updates to localStorage
  const setProvider = (p: string) => {
    setProviderState(p)
    localStorage.setItem('sage_pref_provider', p)
    const conf = PROVIDERS[p]
    if (conf && !conf.isCustomOnly && conf.defaultModel) {
      setModelState(conf.defaultModel)
      localStorage.setItem('sage_pref_model', conf.defaultModel)
    }
  }

  const setModel = (m: string) => {
    setModelState(m)
    localStorage.setItem('sage_pref_model', m)
  }

  const setCustomModel = (cm: string) => {
    setCustomModelState(cm)
    localStorage.setItem('sage_pref_custom_model', cm)
  }

  const setSlidesProvider = (sp: string) => {
    setSlidesProviderState(sp)
    localStorage.setItem('sage_pref_slides_provider', sp)
  }

  const setSlidesModel = (sm: string) => {
    setSlidesModelState(sm)
    localStorage.setItem('sage_pref_slides_model', sm)
  }

  const setCustomSlidesModel = (csm: string) => {
    setCustomSlidesModelState(csm)
    localStorage.setItem('sage_pref_custom_slides_model', csm)
  }

  // Refresh saved keys from backend for signed-in user
  const refreshSavedKeys = useCallback(async () => {
    if (!user) {
      setSavedKeys([])
      return
    }
    try {
      const keys = await getUserSavedKeys()
      setSavedKeys(keys)
    } catch {
      setSavedKeys([])
    }
  }, [user])

  useEffect(() => {
    if (user) {
      refreshSavedKeys()
    } else {
      setSavedKeys([])
    }
  }, [user, refreshSavedKeys])

  // Guest keys in sessionStorage ONLY
  const getGuestKey = (prov: string): string | null => {
    return sessionStorage.getItem(`sage_guest_key_${prov}`)
  }

  const setGuestKey = (prov: string, key: string) => {
    sessionStorage.setItem(`sage_guest_key_${prov}`, key)
  }

  const removeGuestKey = (prov: string) => {
    sessionStorage.removeItem(`sage_guest_key_${prov}`)
  }

  // Save key (signed-in user saves to backend; guest saves to sessionStorage)
  const saveKey = async (prov: string, apiKey: string) => {
    if (user) {
      try {
        const res = await apiSaveUserKey(prov, apiKey)
        await refreshSavedKeys()
        return { ok: true, last4: res.last4 }
      } catch (err: any) {
        return { ok: false, error: err.message || 'Failed to save key' }
      }
    } else {
      setGuestKey(prov, apiKey)
      const last4 = apiKey.length >= 4 ? apiKey.slice(-4) : apiKey
      return { ok: true, last4 }
    }
  }

  const removeKey = async (prov: string) => {
    if (user) {
      try {
        await apiDeleteUserKey(prov)
        await refreshSavedKeys()
        return { ok: true }
      } catch (err: any) {
        return { ok: false, error: err.message || 'Failed to delete key' }
      }
    } else {
      removeGuestKey(prov)
      return { ok: true }
    }
  }

  // Calculate effective models
  const isCustomArticle = model === 'custom' || PROVIDERS[provider]?.isCustomOnly
  const effectiveArticleModel = isCustomArticle ? customModel.trim() : (model || PROVIDERS[provider]?.defaultModel || '')

  const effectiveSlidesProvider = slidesProvider === 'same' ? provider : slidesProvider
  const isCustomSlides = slidesModel === 'custom' || PROVIDERS[effectiveSlidesProvider]?.isCustomOnly
  const effectiveSlidesModel =
    slidesModel === 'same'
      ? effectiveArticleModel
      : isCustomSlides
      ? customSlidesModel.trim()
      : (slidesModel || PROVIDERS[effectiveSlidesProvider]?.defaultModel || '')

  // Key check
  const hasKeyForProvider = (prov: string): boolean => {
    if (prov === 'groq') return true
    if (user && savedKeys.some((k) => k.provider === prov)) return true
    if (Boolean(getGuestKey(prov))) return true
    return false
  }

  // Header display label
  const headerLabel =
    provider === 'groq' && (!model || model === 'openai/gpt-oss-120b')
      ? 'Free model (Groq)'
      : `Model: ${provider} / ${effectiveArticleModel || 'custom'}`

  return (
    <ModelSettingsContext.Provider
      value={{
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
        effectiveSlidesModel,
        savedKeys,
        refreshSavedKeys,
        saveKey,
        removeKey,
        getGuestKey,
        setGuestKey,
        removeGuestKey,
        hasKeyForProvider,
        headerLabel,
        isSettingsOpen,
        setIsSettingsOpen,
        isSignInOpen,
        setIsSignInOpen,
      }}
    >
      {children}
    </ModelSettingsContext.Provider>
  )
}

export function useModelSettings() {
  const ctx = useContext(ModelSettingsContext)
  if (!ctx) {
    throw new Error('useModelSettings must be used within ModelSettingsProvider')
  }
  return ctx
}
