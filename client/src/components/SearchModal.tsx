import React, { useState, useMemo, useEffect, useRef } from 'react'
import { Search, X, MessageSquare } from 'lucide-react'
import { Conversation } from '../types/chat'
import { formatRelativeTime } from '../lib/utils'

interface SearchModalProps {
  open: boolean
  conversations: Conversation[]
  onClose: () => void
  onSelect: (id: string) => void
}

export const SearchModal: React.FC<SearchModalProps> = ({
  open,
  conversations,
  onClose,
  onSelect,
}) => {
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setQuery('')
      window.setTimeout(() => inputRef.current?.focus(), 20)
    }
  }, [open])

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt)
    if (!q) return sorted.slice(0, 12)
    return sorted
      .filter((conv) => {
        if (conv.title.toLowerCase().includes(q)) return true
        return conv.messages.some((m) => m.content.toLowerCase().includes(q))
      })
      .slice(0, 15)
  }, [conversations, query])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4">
      <div
        className="fixed inset-0 bg-stone-950/35 backdrop-blur-xs"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search conversations"
        className="relative z-10 w-full max-w-lg rounded-3xl glass-panel border border-black/[0.08] dark:border-white/[0.12] shadow-glass overflow-hidden animate-slide-up"
      >
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-black/[0.06] dark:border-white/[0.08]">
          <Search className="h-4 w-4 text-stone-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') onClose()
              if (e.key === 'Enter' && results[0]) {
                onSelect(results[0].id)
                onClose()
              }
            }}
            placeholder="Search titles and messages..."
            className="flex-1 bg-transparent text-sm text-stone-950 dark:text-white placeholder:text-stone-400 focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-stone-400 hover:text-stone-800 dark:hover:text-white"
            aria-label="Close search"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {results.length === 0 ? (
            <div className="py-10 text-center text-xs text-stone-400 dark:text-stone-500">
              No matching conversations found.
            </div>
          ) : (
            results.map((conv) => (
              <button
                key={conv.id}
                type="button"
                onClick={() => {
                  onSelect(conv.id)
                  onClose()
                }}
                className="w-full flex items-center justify-between gap-3 rounded-2xl px-3 py-2.5 text-left hover:bg-black/[0.04] dark:hover:bg-white/[0.06] transition focus-ring"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <MessageSquare className="h-4 w-4 text-quince-500 dark:text-quince-400 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-stone-900 dark:text-stone-100 truncate">
                      {conv.title}
                    </div>
                    <div className="text-[11px] text-stone-500 dark:text-stone-400 truncate">
                      {conv.messages[conv.messages.length - 1]?.content || 'Empty thread'}
                    </div>
                  </div>
                </div>
                <span className="font-mono text-[10px] text-stone-400 shrink-0">
                  {formatRelativeTime(conv.updatedAt)}
                </span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
