import React, { useState, useEffect, useCallback, useRef } from 'react'
import { WifiOff, RefreshCw } from 'lucide-react'
import { ChatMessage, TelemetrySnapshot } from './types/chat'
import { useConversations } from './hooks/useConversations'
import { useSettings } from './hooks/useSettings'
import { useBasketSocket } from './hooks/useBasketSocket'
import { fetchTelemetrySnapshot, fetchTtsAudio } from './api/basket'
import { useSound } from './context/SoundContext'
import { useToast } from './context/ToastContext'
import { isEditableElement } from './lib/utils'
import { Sidebar } from './components/Sidebar'
import { Navbar } from './components/Navbar'
import { WelcomeEmptyState } from './components/WelcomeEmptyState'
import { MessageThread } from './components/MessageThread'
import { ComposerDock } from './components/ComposerDock'
import { SearchModal } from './components/SearchModal'
import { SettingsModal } from './components/SettingsModal'

export const App: React.FC = () => {
  const { push } = useToast()
  const { playEnter, playBack, playNotification, playFailed, playScroll } = useSound()
  const { settings, updateSettings } = useSettings()

  const {
    conversations,
    groupedConversations,
    activeId,
    activeConversation,
    setActiveId,
    startNewDraft,
    ensureConversation,
    appendMessage,
    updateMessage,
    truncateFromMessage,
    renameConversation,
    togglePinConversation,
    deleteConversation,
  } = useConversations()

  const {
    connectionState,
    turnState,
    isRecording,
    micLevel,
    sendText,
    sendAwaitUserAnswer,
    startVoice,
    stopVoice,
    cancelTurn,
    stopAudioPlayback,
    reconnectNow,
  } = useBasketSocket({
    onAppendMessage: appendMessage,
    onUpdateMessage: updateMessage,
    onNotifyError: (msg) => push('error', msg),
    onTurnCompleted: playNotification,
    onErrorSound: playFailed,
  })

  const [sidebarOpen, setSidebarOpen] = useState<boolean>(() =>
    typeof window !== 'undefined' ? window.innerWidth >= 1024 : true,
  )
  const [searchOpen, setSearchOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [prefillPrompt, setPrefillPrompt] = useState<string | undefined>(undefined)
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null)
  const messageAudioRef = useRef<HTMLAudioElement | null>(null)

  const [telemetry, setTelemetry] = useState<TelemetrySnapshot>({
    basketReachable: false,
    quinceReachable: false,
    availableModels: [],
    activeModel: settings.model || '',
    lastCheckedAt: 0,
  })

  const refreshTelemetry = useCallback(async () => {
    const snap = await fetchTelemetrySnapshot(settings.model)
    setTelemetry(snap)
  }, [settings.model])

  useEffect(() => {
    void refreshTelemetry()
    const timer = window.setInterval(() => {
      void refreshTelemetry()
    }, 30000)
    return () => window.clearInterval(timer)
  }, [refreshTelemetry])

  const stopMessagePlayback = useCallback(() => {
    if (messageAudioRef.current) {
      messageAudioRef.current.pause()
      messageAudioRef.current = null
    }
    setSpeakingMessageId(null)
  }, [])

  const handleToggleSpeakMessage = useCallback(
    async (message: ChatMessage) => {
      if (speakingMessageId === message.id) {
        stopMessagePlayback()
        return
      }
      stopMessagePlayback()
      setSpeakingMessageId(message.id)

      const { blob, error } = await fetchTtsAudio(message.content, 'jane')
      if (!blob) {
        setSpeakingMessageId((curr) => (curr === message.id ? null : curr))
        playFailed()
        push('error', error || 'Basket TTS is unavailable.')
        return
      }

      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      messageAudioRef.current = audio
      audio.onended = () => {
        URL.revokeObjectURL(url)
        setSpeakingMessageId((curr) => (curr === message.id ? null : curr))
      }
      audio.onerror = () => {
        URL.revokeObjectURL(url)
        setSpeakingMessageId((curr) => (curr === message.id ? null : curr))
        playFailed()
        push('error', 'Failed to play Basket TTS audio.')
      }
      try {
        await audio.play()
      } catch (playErr) {
        URL.revokeObjectURL(url)
        setSpeakingMessageId((curr) => (curr === message.id ? null : curr))
        playFailed()
        push(
          'error',
          playErr instanceof Error
            ? `Audio playback failed: ${playErr.message}`
            : 'Audio playback was blocked.',
        )
      }
    },
    [playFailed, push, speakingMessageId, stopMessagePlayback],
  )

  const handleSendText = useCallback(
    (text: string) => {
      playEnter()
      stopMessagePlayback()
      const conv = ensureConversation(text)
      void sendText(text, conv.id, conv.messages, settings)
    },
    [ensureConversation, playEnter, sendText, settings, stopMessagePlayback],
  )

  const handleStartVoice = useCallback(() => {
    playEnter()
    stopMessagePlayback()
    stopAudioPlayback()
    const conv = ensureConversation('Voice Session')
    void startVoice(conv.id, conv.messages, settings)
  }, [ensureConversation, playEnter, settings, startVoice, stopAudioPlayback, stopMessagePlayback])

  const handleStopVoice = useCallback(() => {
    playBack()
    stopVoice()
  }, [playBack, stopVoice])

  const handleEditAndResend = useCallback(
    (messageId: string, newContent: string) => {
      if (!activeConversation) return
      const idx = activeConversation.messages.findIndex((m) => m.id === messageId)
      if (idx === -1) return
      const priorHistory = activeConversation.messages.slice(0, idx)
      truncateFromMessage(activeConversation.id, messageId)
      playEnter()
      void sendText(newContent, activeConversation.id, priorHistory, settings)
    },
    [activeConversation, playEnter, sendText, settings, truncateFromMessage],
  )

  const handleRegenerate = useCallback(
    (assistantMessageId: string) => {
      if (!activeConversation) return
      const idx = activeConversation.messages.findIndex(
        (m) => m.id === assistantMessageId,
      )
      if (idx <= 0) return
      let userIdx = -1
      for (let i = idx - 1; i >= 0; i -= 1) {
        if (activeConversation.messages[i].role === 'user') {
          userIdx = i
          break
        }
      }
      if (userIdx === -1) return
      const userPrompt = activeConversation.messages[userIdx]
      const priorHistory = activeConversation.messages.slice(0, userIdx)
      truncateFromMessage(activeConversation.id, userPrompt.id)
      playEnter()
      void sendText(userPrompt.content, activeConversation.id, priorHistory, settings)
    },
    [activeConversation, playEnter, sendText, settings, truncateFromMessage],
  )

  const handleNewChat = useCallback(() => {
    playEnter()
    stopMessagePlayback()
    startNewDraft()
    if (typeof window !== 'undefined' && window.innerWidth < 1024) {
      setSidebarOpen(false)
    }
  }, [playEnter, startNewDraft, stopMessagePlayback])

  // Global keyboard shortcuts (Ctrl+K, Ctrl+Shift+O, Ctrl+B, Esc, Y/N confirmations)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey
      if (mod && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchOpen((prev) => !prev)
        return
      }
      if (mod && e.shiftKey && e.key.toLowerCase() === 'o') {
        e.preventDefault()
        handleNewChat()
        return
      }
      if (mod && e.key.toLowerCase() === 'b') {
        e.preventDefault()
        playScroll()
        setSidebarOpen((prev) => !prev)
        return
      }
      if (e.key === 'Escape') {
        if (searchOpen) {
          setSearchOpen(false)
          return
        }
        if (settingsOpen) {
          setSettingsOpen(false)
          return
        }
        if (turnState.phase !== 'idle' || isRecording) {
          e.preventDefault()
          playBack()
          cancelTurn()
        }
        return
      }

      // Y/N quick approval shortcuts during confirmation prompts when not typing in an input
      if (
        !mod &&
        !e.altKey &&
        turnState.phase === 'awaiting_user' &&
        turnState.awaitUser?.kind === 'confirmation' &&
        turnState.awaitUser.status === 'pending' &&
        !isEditableElement(e.target)
      ) {
        const lower = e.key.toLowerCase()
        if (lower === 'y') {
          e.preventDefault()
          playEnter()
          sendAwaitUserAnswer('yes')
        } else if (lower === 'n') {
          e.preventDefault()
          playBack()
          sendAwaitUserAnswer('no')
        }
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [
    cancelTurn,
    handleNewChat,
    isRecording,
    playBack,
    playEnter,
    playScroll,
    searchOpen,
    sendAwaitUserAnswer,
    settingsOpen,
    turnState.awaitUser,
    turnState.phase,
  ])

  const messages = activeConversation?.messages ?? []
  const activeTitle = activeConversation?.title || 'New Chat'

  return (
    <div className="h-screen w-screen overflow-hidden flex bg-[#F8F9F5] dark:bg-[#121310] text-stone-900 dark:text-[#F3F4F1]">
      <Sidebar
        open={sidebarOpen}
        groups={groupedConversations}
        activeId={activeId}
        telemetry={telemetry}
        onCloseMobile={() => setSidebarOpen(false)}
        onSelectConversation={(id) => {
          playScroll()
          setActiveId(id)
          if (typeof window !== 'undefined' && window.innerWidth < 1024) {
            setSidebarOpen(false)
          }
        }}
        onNewChat={handleNewChat}
        onOpenSearch={() => setSearchOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
        onTogglePin={togglePinConversation}
        onRename={renameConversation}
        onDelete={(id) => {
          playBack()
          deleteConversation(id)
        }}
      />

      <main className="relative flex-1 min-w-0 flex flex-col h-full">
        <Navbar
          title={activeTitle}
          canRenameTitle={Boolean(activeConversation)}
          sidebarOpen={sidebarOpen}
          connectionState={connectionState}
          turnPhase={turnState.phase}
          onToggleSidebar={() => {
            playScroll()
            setSidebarOpen((prev) => !prev)
          }}
          onRenameTitle={(nextTitle) => {
            if (activeConversation) renameConversation(activeConversation.id, nextTitle)
          }}
          onOpenSettings={() => setSettingsOpen(true)}
          onReconnect={reconnectNow}
        />

        {connectionState === 'disconnected' && (
          <div className="px-4 py-2 bg-stone-200/75 dark:bg-stone-900/90 border-b border-black/[0.06] dark:border-white/[0.08] flex items-center justify-between gap-2 text-xs">
            <div className="flex items-center gap-2 text-stone-700 dark:text-stone-300">
              <WifiOff className="h-3.5 w-3.5 text-rose-500 shrink-0" />
              <span>
                Basket WebSocket is offline. Live voice &amp; RTSI events require a running Basket Core server; text messages will attempt HTTP SSE fallback.
              </span>
            </div>
            <button
              type="button"
              onClick={reconnectNow}
              className="btn-interactive focus-ring inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[11px] font-semibold bg-white dark:bg-stone-800 border border-black/[0.08] dark:border-white/[0.10] shrink-0"
            >
              <RefreshCw className="h-3 w-3" />
              <span>Retry</span>
            </button>
          </div>
        )}

        <div className="relative flex-1 min-h-0 flex flex-col">
          {messages.length === 0 ? (
            <div className="flex-1 overflow-y-auto pb-36 flex flex-col">
              <WelcomeEmptyState
                connectionState={connectionState}
                activeModel={settings.model || telemetry.activeModel}
                onSelectPrompt={(prompt) => setPrefillPrompt(prompt)}
              />
            </div>
          ) : (
            <MessageThread
              messages={messages}
              turnPhase={turnState.phase}
              isRecording={isRecording}
              speakingMessageId={speakingMessageId}
              onCopy={() => push('success', 'Copied to clipboard', 1800)}
              onEditAndResend={handleEditAndResend}
              onRegenerate={handleRegenerate}
              onToggleSpeakMessage={(msg) => void handleToggleSpeakMessage(msg)}
              onAnswerAwaitUser={(ans) => {
                playEnter()
                sendAwaitUserAnswer(ans)
              }}
              onStartVoiceReply={handleStartVoice}
              onStopVoiceReply={handleStopVoice}
            />
          )}

          <ComposerDock
            turnPhase={turnState.phase}
            isRecording={isRecording}
            micLevel={micLevel}
            transcriptPreview={turnState.transcriptPreview}
            settings={settings}
            prefillPrompt={prefillPrompt}
            onConsumePrefill={() => setPrefillPrompt(undefined)}
            onUpdateSettings={updateSettings}
            onSendText={handleSendText}
            onStartVoice={handleStartVoice}
            onStopVoice={handleStopVoice}
            onCancelTurn={() => {
              playBack()
              cancelTurn()
            }}
          />
        </div>
      </main>

      <SearchModal
        open={searchOpen}
        conversations={conversations}
        onClose={() => setSearchOpen(false)}
        onSelect={(id) => {
          playScroll()
          setActiveId(id)
        }}
      />

      <SettingsModal
        open={settingsOpen}
        settings={settings}
        connectionState={connectionState}
        telemetry={telemetry}
        onClose={() => setSettingsOpen(false)}
        onUpdateSettings={updateSettings}
        onRefreshTelemetry={() => void refreshTelemetry()}
        onReconnectWs={reconnectNow}
      />
    </div>
  )
}

export default App
