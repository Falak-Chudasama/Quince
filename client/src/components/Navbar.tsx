import React, { useState, useEffect } from 'react'
import {
  PanelLeft,
  PanelLeftClose,
  Sun,
  Moon,
  Volume2,
  VolumeX,
  Settings,
  RefreshCw,
} from 'lucide-react'
import { QuinceLogo } from './QuinceLogo'
import { SocketConnectionState, TurnPhase } from '../types/chat'
import { useTheme } from '../context/ThemeContext'
import { useSound } from '../context/SoundContext'

interface NavbarProps {
  title: string
  canRenameTitle: boolean
  sidebarOpen: boolean
  connectionState: SocketConnectionState
  turnPhase: TurnPhase
  onToggleSidebar: () => void
  onRenameTitle: (title: string) => void
  onOpenSettings: () => void
  onReconnect: () => void
}

const PHASE_LABEL: Record<TurnPhase, string> = {
  idle: 'Ready',
  listening: 'Listening',
  transcribing: 'Transcribing',
  thinking: 'Thinking',
  rtsi: 'RTSI Active',
  awaiting_user: 'Needs Input',
  speaking: 'Speaking',
}

export const Navbar: React.FC<NavbarProps> = ({
  title,
  canRenameTitle,
  sidebarOpen,
  connectionState,
  turnPhase,
  onToggleSidebar,
  onRenameTitle,
  onOpenSettings,
  onReconnect,
}) => {
  const { isDark, toggleTheme } = useTheme()
  const { soundEnabled, toggleSound } = useSound()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(title)

  useEffect(() => {
    setDraft(title)
    setEditing(false)
  }, [title])

  const commitTitle = () => {
    setEditing(false)
    if (draft.trim() && draft.trim() !== title) {
      onRenameTitle(draft.trim())
    } else {
      setDraft(title)
    }
  }

  return (
    <header className="h-13 shrink-0 px-3 sm:px-4 py-2 flex items-center justify-between gap-3 border-b border-black/[0.06] dark:border-white/[0.07] bg-[#F8F9F5]/85 dark:bg-[#121310]/85 backdrop-blur-md z-30">
      <div className="flex items-center gap-2 min-w-0">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="btn-interactive focus-ring p-2 rounded-xl text-stone-600 dark:text-stone-300 hover:bg-black/[0.05] dark:hover:bg-white/[0.06]"
          title="Toggle sidebar (Ctrl+B)"
          aria-label="Toggle sidebar"
        >
          {sidebarOpen ? (
            <PanelLeftClose className="h-4 w-4" />
          ) : (
            <PanelLeft className="h-4 w-4" />
          )}
        </button>

        <div className="flex items-center gap-2 min-w-0">
          <QuinceLogo size="sm" />
          {editing ? (
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={commitTitle}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitTitle()
                if (e.key === 'Escape') {
                  setDraft(title)
                  setEditing(false)
                }
              }}
              autoFocus
              className="rounded-lg border border-quince-400/60 bg-white dark:bg-stone-900 px-2 py-0.5 text-sm font-medium text-stone-950 dark:text-white focus:outline-none max-w-[220px]"
            />
          ) : (
            <button
              type="button"
              disabled={!canRenameTitle}
              onClick={() => canRenameTitle && setEditing(true)}
              className={`truncate text-sm font-semibold text-stone-900 dark:text-stone-100 max-w-[180px] sm:max-w-[300px] text-left rounded-md px-1.5 py-0.5 ${
                canRenameTitle
                  ? 'hover:bg-black/[0.04] dark:hover:bg-white/[0.05] cursor-text'
                  : 'cursor-default'
              }`}
              title={canRenameTitle ? 'Click to rename thread' : title}
            >
              {title}
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        {/* Live Connection + Phase Telemetry Pill */}
        <button
          type="button"
          onClick={connectionState === 'disconnected' ? onReconnect : onOpenSettings}
          className="btn-interactive focus-ring inline-flex items-center gap-2 rounded-full surface-card px-2.5 py-1 text-[11px] font-mono text-stone-600 dark:text-stone-300 hover:border-black/[0.12] dark:hover:border-white/[0.16]"
          title={
            connectionState === 'disconnected'
              ? 'Click to reconnect WebSocket'
              : 'Open runtime telemetry'
          }
        >
          <span
            className={`h-2 w-2 rounded-full ${
              turnPhase === 'awaiting_user' || turnPhase === 'rtsi'
                ? 'bg-quince-400 animate-pulse'
                : connectionState === 'connected'
                  ? 'bg-quince-leaf'
                  : connectionState === 'reconnecting' || connectionState === 'connecting'
                    ? 'bg-quince-400 animate-pulse'
                    : 'bg-rose-500'
            }`}
          />
          <span className="hidden sm:inline">
            {connectionState !== 'connected'
              ? connectionState === 'reconnecting'
                ? 'Reconnecting'
                : connectionState === 'connecting'
                  ? 'Connecting'
                  : 'Offline'
              : PHASE_LABEL[turnPhase]}
          </span>
          {connectionState === 'disconnected' && (
            <RefreshCw className="h-3 w-3 text-stone-400" />
          )}
        </button>

        {/* Sound Effects Mute Toggle */}
        <button
          type="button"
          onClick={toggleSound}
          className="btn-interactive focus-ring p-2 rounded-xl text-stone-600 dark:text-stone-300 hover:bg-black/[0.05] dark:hover:bg-white/[0.06]"
          title={soundEnabled ? 'Mute UI & TTS chimes' : 'Unmute UI & TTS chimes'}
          aria-label={soundEnabled ? 'Mute sound' : 'Unmute sound'}
        >
          {soundEnabled ? (
            <Volume2 className="h-4 w-4" />
          ) : (
            <VolumeX className="h-4 w-4 text-stone-400" />
          )}
        </button>

        {/* Light / Dark Mode Switcher (Kiwi / Banana / Cherry pattern) */}
        <button
          type="button"
          onClick={toggleTheme}
          className="focus-ring flex h-8 w-8 items-center justify-center rounded-full text-stone-600 dark:text-stone-300 hover:bg-black/[0.05] dark:hover:bg-white/[0.06] transition"
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {isDark ? (
            <Sun className="h-4 w-4 text-quince-400 transition-transform duration-200 hover:rotate-45" />
          ) : (
            <Moon className="h-4 w-4 text-quince-500 transition-transform duration-200 hover:-rotate-12" />
          )}
        </button>

        <button
          type="button"
          onClick={onOpenSettings}
          className="btn-interactive focus-ring p-2 rounded-xl text-stone-600 dark:text-stone-300 hover:bg-black/[0.05] dark:hover:bg-white/[0.06]"
          title="Settings & telemetry"
          aria-label="Settings"
        >
          <Settings className="h-4 w-4" />
        </button>
      </div>
    </header>
  )
}
