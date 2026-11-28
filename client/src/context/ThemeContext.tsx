import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { ThemePreference } from '../types/chat'

const STORAGE_KEY = 'quince_theme_preference'

interface ThemeContextValue {
  preference: ThemePreference
  resolvedTheme: 'light' | 'dark'
  isDark: boolean
  setPreference: (pref: ThemePreference) => void
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextValue>({
  preference: 'system',
  resolvedTheme: 'light',
  isDark: false,
  setPreference: () => {},
  toggleTheme: () => {},
})

function resolveSystemDark(): boolean {
  if (typeof window === 'undefined') return false
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return true
  }
  const hour = new Date().getHours()
  return hour >= 19 || hour < 6
}

function getInitialPreference(): ThemePreference {
  if (typeof window === 'undefined') return 'system'
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw === 'light' || raw === 'dark' || raw === 'system') return raw
  } catch {
    // ignore storage errors
  }
  return 'system'
}

function applyThemeClass(isDark: boolean): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.toggle('dark', isDark)
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) {
    meta.setAttribute('content', isDark ? '#121310' : '#F8F9F5')
  }
}

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [preference, setPreferenceState] = useState<ThemePreference>(getInitialPreference)
  const [systemDark, setSystemDark] = useState<boolean>(resolveSystemDark)

  const resolvedTheme: 'light' | 'dark' =
    preference === 'dark' || (preference === 'system' && systemDark) ? 'dark' : 'light'
  const isDark = resolvedTheme === 'dark'

  useEffect(() => {
    applyThemeClass(isDark)
  }, [isDark])

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => setSystemDark(resolveSystemDark())
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const setPreference = useCallback((pref: ThemePreference) => {
    setPreferenceState(pref)
    try {
      window.localStorage.setItem(STORAGE_KEY, pref)
    } catch {
      // ignore storage errors
    }
  }, [])

  const toggleTheme = useCallback(() => {
    const next: ThemePreference = isDark ? 'light' : 'dark'
    setPreference(next)
  }, [isDark, setPreference])

  return (
    <ThemeContext.Provider
      value={{
        preference,
        resolvedTheme,
        isDark,
        setPreference,
        toggleTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)
