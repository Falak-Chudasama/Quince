import { useState, useCallback, useEffect } from 'react'
import { BasketSettings } from '../types/chat'
import { DEFAULT_SETTINGS } from '../api/config'

const STORAGE_KEY = 'quince_settings_v1'

function loadSettings(): BasketSettings {
  if (typeof window === 'undefined') return DEFAULT_SETTINGS
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_SETTINGS
    const parsed = JSON.parse(raw) as Partial<BasketSettings>
    return {
      ...DEFAULT_SETTINGS,
      ...parsed,
      voice: 'jane',
    }
  } catch {
    return DEFAULT_SETTINGS
  }
}

export function useSettings() {
  const [settings, setSettingsState] = useState<BasketSettings>(loadSettings)

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    } catch {
      // ignore storage errors
    }
  }, [settings])

  const updateSettings = useCallback((patch: Partial<BasketSettings>) => {
    setSettingsState((prev) => ({
      ...prev,
      ...patch,
      voice: 'jane',
    }))
  }, [])

  return {
    settings,
    updateSettings,
  }
}
