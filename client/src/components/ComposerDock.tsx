import React, { useState, useRef, useEffect } from 'react'
import {
  ArrowUp,
  Square,
  Mic,
  MicOff,
  Brain,
  FileText,
  Volume2,
  VolumeX,
} from 'lucide-react'
import { BasketSettings, TurnPhase } from '../types/chat'

interface ComposerDockProps {
  turnPhase: TurnPhase
  isRecording: boolean
  micLevel: number
  transcriptPreview: string
  settings: BasketSettings
  prefillPrompt?: string
  onConsumePrefill?: () => void
  onUpdateSettings: (patch: Partial<BasketSettings>) => void
  onSendText: (text: string) => void
  onStartVoice: () => void
  onStopVoice: () => void
  onCancelTurn: () => void
}

const WAVEFORM_MULTIPLIERS = [0.45, 0.85, 1.0, 0.72, 0.5]

export const ComposerDock: React.FC<ComposerDockProps> = ({
  turnPhase,
  isRecording,
  micLevel,
  transcriptPreview,
  settings,
  prefillPrompt,
  onConsumePrefill,
  onUpdateSettings,
  onSendText,
  onStartVoice,
  onStopVoice,
  onCancelTurn,
}) => {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const isBusy =
    turnPhase === 'thinking' ||
    turnPhase === 'rtsi' ||
    turnPhase === 'speaking' ||
    turnPhase === 'transcribing'

  useEffect(() => {
    if (prefillPrompt) {
      setInput(prefillPrompt)
      onConsumePrefill?.()
      window.setTimeout(() => {
        textareaRef.current?.focus()
      }, 20)
    }
  }, [prefillPrompt, onConsumePrefill])

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 196)}px`
  }, [input])

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed) return
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    onSendText(trimmed)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isBusy && input.trim()) {
        handleSend()
      }
    }
  }

  return (
    <div className="pointer-events-none absolute bottom-0 inset-x-0 px-3 sm:px-6 pb-4 pt-6 bg-gradient-to-t from-[#F8F9F5] via-[#F8F9F5]/90 to-transparent dark:from-[#121310] dark:via-[#121310]/90 z-20">
      <div className="pointer-events-auto mx-auto max-w-3xl">
        {(isRecording || transcriptPreview) && (
          <div className="mb-2 mx-auto w-fit max-w-full rounded-full glass-capsule border border-black/[0.08] dark:border-white/[0.12] px-3.5 py-1.5 flex items-center gap-2.5 text-xs shadow-soft">
            {isRecording && (
              <div className="flex items-center gap-0.5 h-3.5" aria-hidden="true">
                {WAVEFORM_MULTIPLIERS.map((mult, idx) => {
                  const pct = Math.max(22, Math.min(100, Math.round(micLevel * 100 * mult)))
                  return (
                    <span
                      key={idx}
                      style={{ height: `${pct}%` }}
                      className="w-0.5 rounded-full bg-rose-500 transition-[height] duration-75"
                    />
                  )
                })}
              </div>
            )}
            <span className="font-mono text-[11px] text-stone-700 dark:text-stone-200 truncate max-w-sm">
              {transcriptPreview || 'Listening for speech (16kHz PCM16)...'}
            </span>
          </div>
        )}

        <div className="rounded-3xl glass-panel border border-black/[0.08] dark:border-white/[0.11] shadow-glass px-3.5 pt-2.5 pb-2 transition-shadow focus-within:border-quince-400/60 dark:focus-within:border-quince-400/50">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              turnPhase === 'awaiting_user'
                ? 'Type your answer to Quince...'
                : 'Message Quince or start voice...'
            }
            aria-label="Message Quince"
            className="w-full max-h-[196px] overflow-y-auto resize-none bg-transparent px-1.5 py-1 text-[15px] leading-relaxed text-stone-950 dark:text-stone-50 placeholder:text-stone-400 dark:placeholder:text-stone-500 focus:outline-none"
          />

          <div className="mt-1.5 flex items-center justify-between gap-2 pt-1">
            {/* Compact Context & Voice Toggles */}
            <div className="flex items-center gap-1 overflow-x-auto [scrollbar-width:none]">
              <button
                type="button"
                onClick={() =>
                  onUpdateSettings({ retrieveChat: !settings.retrieveChat })
                }
                className={`btn-interactive focus-ring inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium border transition ${
                  settings.retrieveChat
                    ? 'border-quince-400/45 bg-quince-100/70 dark:bg-quince-400/15 text-quince-600 dark:text-quince-300'
                    : 'border-black/[0.06] dark:border-white/[0.08] text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-200'
                }`}
                title="Include chat memory retrieval"
              >
                <Brain className="h-3 w-3" />
                <span>Memory</span>
              </button>

              <button
                type="button"
                onClick={() =>
                  onUpdateSettings({ retrieveNotes: !settings.retrieveNotes })
                }
                className={`btn-interactive focus-ring inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium border transition ${
                  settings.retrieveNotes
                    ? 'border-quince-leaf/50 bg-quince-leaf/15 text-quince-leaf-dark dark:text-quince-leaf'
                    : 'border-black/[0.06] dark:border-white/[0.08] text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-200'
                }`}
                title="Include Basket notes RAG"
              >
                <FileText className="h-3 w-3" />
                <span>Notes</span>
              </button>

              <button
                type="button"
                onClick={() =>
                  onUpdateSettings({ synthesizeSpeech: !settings.synthesizeSpeech })
                }
                className={`btn-interactive focus-ring inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium border transition ${
                  settings.synthesizeSpeech
                    ? 'border-stone-900/20 dark:border-white/25 bg-stone-900/[0.06] dark:bg-white/[0.08] text-stone-900 dark:text-white'
                    : 'border-black/[0.06] dark:border-white/[0.08] text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-200'
                }`}
                title="Auto-speak replies via TTS"
              >
                {settings.synthesizeSpeech ? (
                  <Volume2 className="h-3 w-3" />
                ) : (
                  <VolumeX className="h-3 w-3" />
                )}
                <span>Voice reply</span>
              </button>
            </div>

            {/* Mic + Send/Stop Morph */}
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                onClick={isRecording ? onStopVoice : onStartVoice}
                disabled={isBusy && !isRecording}
                className={`btn-interactive focus-ring inline-flex items-center justify-center h-8 w-8 rounded-full border transition ${
                  isRecording
                    ? 'bg-rose-500 border-rose-500 text-white shadow-soft'
                    : 'border-black/[0.07] dark:border-white/[0.10] bg-stone-100/80 dark:bg-stone-850 text-stone-700 dark:text-stone-200 hover:bg-stone-200/80 dark:hover:bg-stone-800 disabled:opacity-40'
                }`}
                title={isRecording ? 'Stop recording' : 'Start voice input'}
                aria-label={isRecording ? 'Stop recording' : 'Start voice input'}
              >
                {isRecording ? (
                  <MicOff className="h-4 w-4" />
                ) : (
                  <Mic className="h-4 w-4" />
                )}
              </button>

              {isBusy ? (
                <button
                  type="button"
                  onClick={onCancelTurn}
                  className="btn-interactive focus-ring inline-flex items-center justify-center h-8 w-8 rounded-full bg-stone-950 text-white dark:bg-white dark:text-stone-950 hover:opacity-90"
                  title="Stop generation (Esc)"
                  aria-label="Stop generation"
                >
                  <Square className="h-3.5 w-3.5 fill-current" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="btn-interactive focus-ring inline-flex items-center justify-center h-8 w-8 rounded-full bg-stone-950 text-white dark:bg-quince-400 dark:text-stone-950 disabled:opacity-30 hover:opacity-90"
                  title="Send message (Enter)"
                  aria-label="Send message"
                >
                  <ArrowUp className="h-4 w-4 stroke-[2.25]" />
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="mt-1.5 flex items-center justify-between px-3 text-[10px] font-mono text-stone-400 dark:text-stone-500">
          <span>Enter to send · Shift+Enter for newline · Esc to stop</span>
          <span className="hidden sm:inline">Ctrl+K search · Ctrl+Shift+O new</span>
        </div>
      </div>
    </div>
  )
}
