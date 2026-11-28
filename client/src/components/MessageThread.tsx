import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Check,
  Copy,
  RotateCcw,
  Pencil,
  Volume2,
  Square,
  ArrowDown,
  AlertTriangle,
} from 'lucide-react'
import { ChatMessage, TurnPhase } from '../types/chat'
import { formatRelativeTime } from '../lib/utils'
import { QuinceLogo } from './QuinceLogo'
import { MarkdownRenderer } from './MarkdownRenderer'
import { RtsiTimelineCard } from './RtsiTimelineCard'
import { AwaitUserCard } from './AwaitUserCard'

interface MessageThreadProps {
  messages: ChatMessage[]
  turnPhase: TurnPhase
  isRecording: boolean
  speakingMessageId: string | null
  onCopy: (content: string) => void
  onEditAndResend: (messageId: string, newContent: string) => void
  onRegenerate: (assistantMessageId: string) => void
  onToggleSpeakMessage: (message: ChatMessage) => void
  onAnswerAwaitUser: (answer: string) => void
  onStartVoiceReply: () => void
  onStopVoiceReply: () => void
}

export const MessageThread: React.FC<MessageThreadProps> = ({
  messages,
  turnPhase,
  isRecording,
  speakingMessageId,
  onCopy,
  onEditAndResend,
  onRegenerate,
  onToggleSpeakMessage,
  onAnswerAwaitUser,
  onStartVoiceReply,
  onStopVoiceReply,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const [isNearBottom, setIsNearBottom] = useState(true)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState('')

  const scrollToBottom = useCallback((smooth = true) => {
    if (endRef.current) {
      endRef.current.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto' })
      setIsNearBottom(true)
    }
  }, [])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    setIsNearBottom(distance < 96)
  }

  useEffect(() => {
    if (isNearBottom) {
      scrollToBottom(false)
    }
  }, [messages, isNearBottom, scrollToBottom])

  const triggerCopy = async (id: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // ignore clipboard error in headless test environments
    }
    onCopy(text)
    setCopiedId(id)
    window.setTimeout(() => {
      setCopiedId((prev) => (prev === id ? null : prev))
    }, 1800)
  }

  const startEditing = (msg: ChatMessage) => {
    setEditingId(msg.id)
    setEditDraft(msg.content)
  }

  const submitEdit = (messageId: string) => {
    const trimmed = editDraft.trim()
    if (!trimmed) return
    setEditingId(null)
    onEditAndResend(messageId, trimmed)
  }

  return (
    <div className="relative flex-1 min-h-0 flex flex-col">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 sm:px-6 pt-4 pb-36"
      >
        <div className="mx-auto max-w-3xl space-y-6">
          {messages.map((msg) => {
            const isUser = msg.role === 'user'
            const isEditing = editingId === msg.id
            const isSpeakingThis = speakingMessageId === msg.id

            if (isUser) {
              return (
                <div key={msg.id} className="group flex flex-col items-end">
                  <div className="max-w-[85%] sm:max-w-[78%] rounded-2xl surface-card px-4 py-3 shadow-2xs">
                    {isEditing ? (
                      <div className="space-y-2 min-w-[240px] sm:min-w-[340px]">
                        <textarea
                          value={editDraft}
                          onChange={(e) => setEditDraft(e.target.value)}
                          rows={3}
                          className="w-full rounded-xl border border-black/[0.08] dark:border-white/[0.12] bg-stone-50 dark:bg-stone-950 px-3 py-2 text-sm text-stone-900 dark:text-stone-100 focus-ring resize-y"
                        />
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => setEditingId(null)}
                            className="btn-interactive rounded-lg px-2.5 py-1 text-xs text-stone-500 hover:text-stone-800 dark:hover:text-stone-200"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={() => submitEdit(msg.id)}
                            className="btn-interactive rounded-lg px-3 py-1 text-xs font-semibold bg-stone-900 text-white dark:bg-quince-400 dark:text-stone-950"
                          >
                            Save &amp; Resend
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-[15px] leading-relaxed text-stone-900 dark:text-stone-100 whitespace-pre-wrap break-words">
                        {msg.content}
                      </p>
                    )}
                  </div>

                  {!isEditing && (
                    <div className="mt-1.5 flex items-center gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity text-[11px] text-stone-400 dark:text-stone-500">
                      <span className="font-mono mr-1">
                        {formatRelativeTime(msg.createdAt)}
                      </span>
                      <button
                        type="button"
                        onClick={() => triggerCopy(msg.id, msg.content)}
                        className="p-1 rounded-md hover:bg-black/[0.04] dark:hover:bg-white/[0.06] hover:text-stone-700 dark:hover:text-stone-200 transition focus-ring"
                        title="Copy message"
                        aria-label="Copy message"
                      >
                        {copiedId === msg.id ? (
                          <Check className="h-3.5 w-3.5 text-quince-leaf-dark dark:text-quince-leaf" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => startEditing(msg)}
                        disabled={turnPhase !== 'idle'}
                        className="p-1 rounded-md hover:bg-black/[0.04] dark:hover:bg-white/[0.06] hover:text-stone-700 dark:hover:text-stone-200 transition disabled:opacity-40 focus-ring"
                        title="Edit and resend"
                        aria-label="Edit and resend"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              )
            }

            const hasRtsi = Boolean(msg.rtsiSteps && msg.rtsiSteps.length > 0)

            return (
              <div key={msg.id} className="group flex items-start gap-3">
                <div className="mt-0.5 h-7 w-7 rounded-xl surface-card shadow-2xs flex items-center justify-center shrink-0">
                  <QuinceLogo size="xs" breathing={msg.isStreaming} />
                </div>

                <div className="min-w-0 flex-1">
                  {hasRtsi && (
                    <RtsiTimelineCard
                      steps={msg.rtsiSteps!}
                      isLive={Boolean(msg.isStreaming)}
                    />
                  )}

                  {msg.awaitUser && (
                    <AwaitUserCard
                      prompt={msg.awaitUser}
                      isRecording={isRecording}
                      onAnswer={onAnswerAwaitUser}
                      onStartVoiceReply={onStartVoiceReply}
                      onStopVoiceReply={onStopVoiceReply}
                    />
                  )}

                  {msg.content ? (
                    <MarkdownRenderer
                      content={msg.content}
                      isStreaming={Boolean(msg.isStreaming)}
                    />
                  ) : msg.isStreaming ? (
                    <div className="flex items-center gap-2 py-1 text-xs font-mono text-stone-500 dark:text-stone-400">
                      <span className="inline-flex gap-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-quince-400 animate-bounce [animation-delay:-0.2s]" />
                        <span className="h-1.5 w-1.5 rounded-full bg-quince-400 animate-bounce [animation-delay:-0.1s]" />
                        <span className="h-1.5 w-1.5 rounded-full bg-quince-400 animate-bounce" />
                      </span>
                      <span>
                        {turnPhase === 'rtsi'
                          ? 'Executing browser workflow...'
                          : turnPhase === 'awaiting_user'
                            ? 'Waiting for your response...'
                            : turnPhase === 'transcribing'
                              ? 'Transcribing speech...'
                              : 'Thinking...'}
                      </span>
                    </div>
                  ) : !msg.error && !hasRtsi && !msg.awaitUser ? (
                    <p className="text-xs italic text-stone-400 dark:text-stone-500 py-1">
                      Interrupted before a response was received. Use Regenerate to retry.
                    </p>
                  ) : null}

                  {msg.error && (
                    <div className="mt-2.5 flex items-center gap-2 rounded-xl border border-rose-500/25 bg-rose-500/[0.07] px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-rose-500" />
                      <span className="flex-1">{msg.error}</span>
                    </div>
                  )}

                  {!msg.isStreaming && (
                    <div className="mt-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity text-[11px] text-stone-400 dark:text-stone-500">
                      <button
                        type="button"
                        onClick={() => triggerCopy(msg.id, msg.content)}
                        disabled={!msg.content}
                        className="p-1.5 rounded-lg hover:bg-black/[0.04] dark:hover:bg-white/[0.06] hover:text-stone-800 dark:hover:text-stone-200 transition disabled:opacity-40 focus-ring"
                        title="Copy reply"
                        aria-label="Copy reply"
                      >
                        {copiedId === msg.id ? (
                          <Check className="h-3.5 w-3.5 text-quince-leaf-dark dark:text-quince-leaf" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>

                      <button
                        type="button"
                        onClick={() => onRegenerate(msg.id)}
                        disabled={turnPhase !== 'idle'}
                        className="p-1.5 rounded-lg hover:bg-black/[0.04] dark:hover:bg-white/[0.06] hover:text-stone-800 dark:hover:text-stone-200 transition disabled:opacity-40 focus-ring"
                        title="Regenerate response"
                        aria-label="Regenerate response"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                      </button>

                      <button
                        type="button"
                        onClick={() => onToggleSpeakMessage(msg)}
                        disabled={!msg.content}
                        className={`p-1.5 rounded-lg transition disabled:opacity-40 focus-ring ${
                          isSpeakingThis
                            ? 'bg-quince-400/20 text-quince-600 dark:text-quince-300'
                            : 'hover:bg-black/[0.04] dark:hover:bg-white/[0.06] hover:text-stone-800 dark:hover:text-stone-200'
                        }`}
                        title={isSpeakingThis ? 'Stop reading aloud' : 'Read aloud'}
                        aria-label={isSpeakingThis ? 'Stop reading aloud' : 'Read aloud'}
                      >
                        {isSpeakingThis ? (
                          <Square className="h-3.5 w-3.5" />
                        ) : (
                          <Volume2 className="h-3.5 w-3.5" />
                        )}
                      </button>

                      <span className="ml-1.5 font-mono">
                        {formatRelativeTime(msg.createdAt)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
          <div ref={endRef} />
        </div>
      </div>

      {!isNearBottom && (
        <div className="pointer-events-none absolute bottom-32 inset-x-0 flex justify-center z-20">
          <button
            type="button"
            onClick={() => scrollToBottom(true)}
            className="pointer-events-auto btn-interactive focus-ring inline-flex items-center gap-1.5 rounded-full glass-capsule border border-black/[0.08] dark:border-white/[0.12] px-3 py-1.5 text-xs font-medium text-stone-700 dark:text-stone-200 shadow-glass"
          >
            <ArrowDown className="h-3.5 w-3.5" />
            <span>Scroll to bottom</span>
          </button>
        </div>
      )}
    </div>
  )
}
