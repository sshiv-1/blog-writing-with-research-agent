const GUEST_KEY_PREFIX = 'sage_guest_key_'

export function getStoredGuestKey(provider: string): string | null {
  try {
    return sessionStorage.getItem(`${GUEST_KEY_PREFIX}${provider}`)
  } catch {
    return null
  }
}

export function setStoredGuestKey(provider: string, key: string): void {
  try {
    sessionStorage.setItem(`${GUEST_KEY_PREFIX}${provider}`, key)
  } catch {
    // Ignore storage quota / disabled storage errors
  }
}

export function removeStoredGuestKey(provider: string): void {
  try {
    sessionStorage.removeItem(`${GUEST_KEY_PREFIX}${provider}`)
  } catch {
    // Ignore storage errors
  }
}

export function clearAllGuestKeys(): void {
  try {
    const toRemove: string[] = []
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i)
      if (k && k.startsWith(GUEST_KEY_PREFIX)) {
        toRemove.push(k)
      }
    }
    for (const k of toRemove) {
      sessionStorage.removeItem(k)
    }
  } catch {
    // Ignore storage errors
  }
}
