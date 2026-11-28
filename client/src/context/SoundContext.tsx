import React, { createContext, useContext, useState, useCallback } from 'react'
import {
  isSoundEnabled,
  setSoundEnabled,
  playEnter,
  playBack,
  playNotification,
  playFailed,
  playScroll,
} from '../lib/sound'

interface SoundContextType {
  soundEnabled: boolean
  toggleSound: () => void
  setSound: (enabled: boolean) => void
  playEnter: () => void
  playBack: () => void
  playNotification: () => void
  playFailed: () => void
  playScroll: () => void
}

const SoundContext = createContext<SoundContextType>({
  soundEnabled: true,
  toggleSound: () => {},
  setSound: () => {},
  playEnter: () => {},
  playBack: () => {},
  playNotification: () => {},
  playFailed: () => {},
  playScroll: () => {},
})

export const SoundProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [soundEnabled, setSoundState] = useState<boolean>(isSoundEnabled)

  const setSound = useCallback((enabled: boolean) => {
    setSoundEnabled(enabled)
    setSoundState(enabled)
  }, [])

  const toggleSound = useCallback(() => {
    setSoundState((prev) => {
      const next = !prev
      setSoundEnabled(next)
      return next
    })
  }, [])

  return (
    <SoundContext.Provider
      value={{
        soundEnabled,
        toggleSound,
        setSound,
        playEnter,
        playBack,
        playNotification,
        playFailed,
        playScroll,
      }}
    >
      {children}
    </SoundContext.Provider>
  )
}

export const useSound = () => useContext(SoundContext)
