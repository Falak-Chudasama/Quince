import React, { useState } from 'react'
import { ShieldAlert, HelpCircle, Check, X, Send, Mic, Square } from 'lucide-react'
import { AwaitUserPrompt } from '../types/chat'

interface AwaitUserCardProps {
  prompt: AwaitUserPrompt
  isRecording: boolean
  onAnswer: (answer: string) => void
  onStartVoiceReply: () => void
  onStopVoiceReply: () => void
}

export const AwaitUserCard: React.FC<AwaitUserCardProps> = ({
  prompt,
  isRecording,
  onAnswer,
  onStartVoiceReply,
  onStopVoiceReply,
}) => {
  const [replyText, setReplyText] = useState('')
  const isConfirmation = prompt.kind === 'confirmation'
  const isAnswered = prompt.status === 'answered'

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!replyText.trim() || isAnswered) return
    onAnswer(replyText.trim())
    setReplyText('')
  }

  return (
    <div
      className={`my-3 rounded-2xl border p-4 transition ${
        isAnswered
          ? 'surface-card opacity-85'
          : 'bg-quince-50/75 dark:bg-stone-900 border-quince-400/55 dark:border-quince-400/40 shadow-soft'
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`mt-0.5 h-8 w-8 rounded-xl flex items-center justify-center shrink-0 ${
            isAnswered
              ? 'bg-quince-leaf/20 text-quince-leaf-dark dark:text-quince-leaf'
              : 'bg-quince-200/80 dark:bg-quince-400/20 text-quince-600 dark:text-quince-300'
          }`}
        >
          {isAnswered ? (
            <Check className="h-4 w-4" />
          ) : isConfirmation ? (
            <ShieldAlert className="h-4 w-4" />
          ) : (
            <HelpCircle className="h-4 w-4" />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-[11px] uppercase tracking-wider text-quince-600 dark:text-quince-400 font-semibold">
              {isAnswered
                ? 'Response recorded'
                : isConfirmation
                  ? 'Confirmation required'
                  : 'Input requested'}
            </span>
            {!isAnswered && isConfirmation && (
              <span className="hidden sm:inline-block font-mono text-[10px] text-stone-500 dark:text-stone-400">
                Press Y / N
              </span>
            )}
          </div>

          <p className="mt-1 text-sm text-stone-900 dark:text-stone-100 leading-relaxed">
            {prompt.question}
          </p>

          {isAnswered && prompt.answer ? (
            <div className="mt-2.5 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium bg-stone-900/[0.06] dark:bg-white/[0.08] text-stone-700 dark:text-stone-200">
              <span>Answered:</span>
              <span className="font-semibold">{prompt.answer}</span>
            </div>
          ) : (
            <div className="mt-3 space-y-2.5">
              {isConfirmation && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onAnswer('yes')}
                    className="btn-interactive focus-ring inline-flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold bg-stone-900 text-white dark:bg-quince-400 dark:text-stone-950 hover:opacity-90"
                  >
                    <Check className="h-3.5 w-3.5" />
                    <span>Approve (Yes)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onAnswer('no')}
                    className="btn-interactive focus-ring inline-flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold border border-black/[0.09] dark:border-white/[0.12] bg-white dark:bg-stone-850 text-stone-700 dark:text-stone-200 hover:bg-stone-100 dark:hover:bg-stone-800"
                  >
                    <X className="h-3.5 w-3.5" />
                    <span>Decline (No)</span>
                  </button>
                </div>
              )}

              <form onSubmit={handleSubmit} className="flex items-center gap-2">
                <input
                  type="text"
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder={
                    isConfirmation
                      ? 'Or type a specific instruction...'
                      : 'Type your answer...'
                  }
                  className="flex-1 rounded-xl border border-black/[0.08] dark:border-white/[0.10] bg-white dark:bg-stone-950 px-3 py-2 text-xs text-stone-900 dark:text-stone-100 placeholder:text-stone-400 dark:placeholder:text-stone-500 focus-ring"
                />
                <button
                  type="button"
                  onClick={isRecording ? onStopVoiceReply : onStartVoiceReply}
                  className={`btn-interactive focus-ring inline-flex items-center justify-center rounded-xl p-2 border ${
                    isRecording
                      ? 'bg-rose-500 border-rose-500 text-white animate-pulse'
                      : 'border-black/[0.08] dark:border-white/[0.10] bg-white dark:bg-stone-850 text-stone-600 dark:text-stone-300 hover:text-stone-900 dark:hover:text-white'
                  }`}
                  title={isRecording ? 'Stop voice answer' : 'Answer by voice'}
                  aria-label={isRecording ? 'Stop voice answer' : 'Answer by voice'}
                >
                  {isRecording ? (
                    <Square className="h-3.5 w-3.5" />
                  ) : (
                    <Mic className="h-3.5 w-3.5" />
                  )}
                </button>
                <button
                  type="submit"
                  disabled={!replyText.trim()}
                  className="btn-interactive focus-ring inline-flex items-center gap-1 rounded-xl px-3 py-2 text-xs font-semibold bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-950 disabled:opacity-40"
                >
                  <Send className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Send</span>
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
