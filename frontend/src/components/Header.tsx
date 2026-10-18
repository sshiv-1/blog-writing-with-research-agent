import { useState, useRef, useEffect, type ReactNode } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Cpu, History, Settings, LogOut, ChevronDown } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useModelSettings } from '@/context/ModelSettingsContext'
import SignInModal from './SignInModal'
import SettingsModal from './SettingsModal'

interface HeaderProps {
  leftSlot?: ReactNode
  rightSlot?: ReactNode
}

export default function Header({ leftSlot, rightSlot }: HeaderProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, isConfigured, signOut } = useAuth()
  const {
    headerLabel,
    isSettingsOpen,
    setIsSettingsOpen,
    isSignInOpen,
    setIsSignInOpen,
  } = useModelSettings()

  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSignOut = async () => {
    setIsMenuOpen(false)
    await signOut()
    // If signed out while on history or a private result, navigate to home
    if (location.pathname.startsWith('/history') || location.pathname.startsWith('/result')) {
      navigate('/')
    }
  }

  // User initials
  const userInitial = user?.email ? user.email[0].toUpperCase() : 'U'

  return (
    <>
      <header
        className="sticky top-0 z-40 flex items-center h-14 px-4 sm:px-6"
        style={{
          background: 'var(--color-overlay)',
          borderBottom: '1px solid var(--color-border)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
        }}
      >
        <div className="w-full max-w-6xl mx-auto flex items-center justify-between gap-3">
          {/* Left section: Optional slot (e.g. back button) + Brand Wordmark */}
          <div className="flex items-center gap-3">
            {leftSlot}

            <Link
              to="/"
              className="flex items-center gap-2 text-decoration-none group focus:outline-none"
            >
              <span
                className="text-sm font-semibold tracking-tight transition-colors group-hover:text-[var(--color-accent)]"
                style={{ color: 'var(--color-ink)', letterSpacing: '-0.02em' }}
              >
                SAGE
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
            </Link>
          </div>

          {/* Right section: Slots, Model pill, and Auth/Avatar menu */}
          <div className="flex items-center gap-2 sm:gap-3">
            {rightSlot}

            {/* Model indicator pill */}
            <button
              type="button"
              onClick={() => setIsSettingsOpen(true)}
              aria-label="Open model settings"
              className="flex items-center gap-1.5 h-8 px-2.5 sm:px-3 text-xs font-medium rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-ink-2)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-ink)] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] cursor-pointer"
            >
              <Cpu className="w-3.5 h-3.5 text-[var(--color-accent)]" />
              <span className="hidden sm:inline font-mono text-[0.6875rem]">
                {headerLabel}
              </span>
              <span className="sm:hidden font-mono text-[0.6875rem]">Model</span>
            </button>

            {/* Auth Controls (hidden when Supabase is not configured per amendment 5) */}
            {isConfigured && (
              <>
                {user ? (
                  /* Signed-in user avatar and menu */
                  <div className="relative" ref={menuRef}>
                    <button
                      type="button"
                      onClick={() => setIsMenuOpen(!isMenuOpen)}
                      aria-expanded={isMenuOpen}
                      aria-haspopup="true"
                      className="flex items-center gap-1.5 h-8 pl-1.5 pr-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-border-strong)] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] cursor-pointer"
                    >
                      <div className="w-5 h-5 rounded-full bg-[var(--color-accent)] text-[var(--color-ink-inv)] text-[0.6875rem] font-bold flex items-center justify-center">
                        {userInitial}
                      </div>
                      <ChevronDown className="w-3 h-3 text-[var(--color-ink-3)]" />
                    </button>

                    {/* Dropdown Menu */}
                    {isMenuOpen && (
                      <div
                        role="menu"
                        className="absolute right-0 mt-1.5 w-56 rounded-xl border border-[var(--color-border)] bg-[var(--color-elevated)] shadow-lg py-1.5 z-50 text-xs transition-all"
                        style={{
                          background: 'var(--color-elevated)',
                          borderColor: 'var(--color-border)',
                        }}
                      >
                        <div className="px-3.5 py-2 border-b border-[var(--color-border)]">
                          <p className="font-semibold text-[var(--color-ink)] truncate">{user.email}</p>
                          <p className="text-[0.6875rem] text-[var(--color-ink-4)] mt-0.5">Signed in</p>
                        </div>

                        <div className="py-1">
                          <button
                            type="button"
                            role="menuitem"
                            onClick={() => {
                              setIsMenuOpen(false)
                              navigate('/history')
                            }}
                            className="w-full flex items-center gap-2.5 px-3.5 py-2 text-left text-[var(--color-ink)] hover:bg-[var(--color-surface)] transition-colors focus:outline-none"
                          >
                            <History className="w-4 h-4 text-[var(--color-ink-3)]" />
                            Article History
                          </button>

                          <button
                            type="button"
                            role="menuitem"
                            onClick={() => {
                              setIsMenuOpen(false)
                              setIsSettingsOpen(true)
                            }}
                            className="w-full flex items-center gap-2.5 px-3.5 py-2 text-left text-[var(--color-ink)] hover:bg-[var(--color-surface)] transition-colors focus:outline-none"
                          >
                            <Settings className="w-4 h-4 text-[var(--color-ink-3)]" />
                            Model Settings
                          </button>
                        </div>

                        <div className="border-t border-[var(--color-border)] pt-1">
                          <button
                            type="button"
                            role="menuitem"
                            onClick={handleSignOut}
                            className="w-full flex items-center gap-2.5 px-3.5 py-2 text-left text-[var(--color-error)] hover:bg-[var(--color-error-bg)] transition-colors focus:outline-none"
                          >
                            <LogOut className="w-4 h-4" />
                            Sign out
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  /* Guest: Quiet Sign in button */
                  <button
                    type="button"
                    onClick={() => setIsSignInOpen(true)}
                    className="h-8 px-3 text-xs font-medium rounded-lg text-[var(--color-ink-2)] hover:text-[var(--color-ink)] hover:bg-[var(--color-surface)] border border-transparent hover:border-[var(--color-border)] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] cursor-pointer"
                  >
                    Sign in
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </header>

      {/* Mount Modals */}
      <SignInModal isOpen={isSignInOpen} onClose={() => setIsSignInOpen(false)} />
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </>
  )
}
