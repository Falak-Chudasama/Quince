import React, { useState } from 'react'
import {
  Plus,
  Search,
  Pin,
  PinOff,
  Pencil,
  Trash2,
  Settings,
  X,
  Check,
} from 'lucide-react'
import {
  Conversation,
  ConversationGroup,
  TelemetrySnapshot,
} from '../types/chat'
import { QuinceLogo } from './QuinceLogo'

interface SidebarProps {
  open: boolean
  groups: ConversationGroup[]
  activeId: string | null
  telemetry: TelemetrySnapshot
  onCloseMobile: () => void
  onSelectConversation: (id: string) => void
  onNewChat: () => void
  onOpenSearch: () => void
  onOpenSettings: () => void
  onTogglePin: (id: string) => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
}

export const Sidebar: React.FC<SidebarProps> = ({
  open,
  groups,
  activeId,
  telemetry,
  onCloseMobile,
  onSelectConversation,
  onNewChat,
  onOpenSearch,
  onOpenSettings,
  onTogglePin,
  onRename,
  onDelete,
}) => {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  const startRename = (e: React.MouseEvent, conv: Conversation) => {
    e.stopPropagation()
    setEditingId(conv.id)
    setEditTitle(conv.title)
  }

  const commitRename = (id: string) => {
    if (editTitle.trim()) {
      onRename(id, editTitle.trim())
    }
    setEditingId(null)
  }

  const railContent = (
    <div className="flex flex-col h-full w-64 bg-[#F1F3EE]/90 dark:bg-[#151613]/95 border-r border-black/[0.06] dark:border-white/[0.07]">
      {/* Brand + Close on mobile */}
      <div className="px-3.5 pt-3.5 pb-2 flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2">
          <QuinceLogo size="sm" />
          <span className="font-display text-sm font-semibold tracking-tight text-stone-950 dark:text-white">
            Quince
          </span>
        </div>
        <button
          type="button"
          onClick={onCloseMobile}
          className="lg:hidden p-1.5 rounded-lg text-stone-500 hover:text-stone-900 dark:hover:text-white"
          aria-label="Close sidebar"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Primary Actions: New Chat & Quick Search */}
      <div className="px-3 py-2 space-y-1.5 shrink-0">
        <button
          type="button"
          onClick={onNewChat}
          className="btn-interactive focus-ring w-full flex items-center justify-between gap-2 rounded-xl px-3 py-2 text-xs font-semibold bg-stone-950 text-white dark:bg-stone-100 dark:text-stone-950 hover:opacity-90 shadow-2xs"
        >
          <span className="inline-flex items-center gap-2">
            <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
            <span>New chat</span>
          </span>
          <kbd className="font-mono text-[10px] opacity-65">Ctrl+⇧+O</kbd>
        </button>

        <button
          type="button"
          onClick={onOpenSearch}
          className="btn-interactive focus-ring w-full flex items-center justify-between gap-2 rounded-xl px-3 py-2 text-xs text-stone-600 dark:text-stone-300 surface-card hover:border-black/[0.12] dark:hover:border-white/[0.15]"
        >
          <span className="inline-flex items-center gap-2">
            <Search className="h-3.5 w-3.5 text-stone-400" />
            <span>Search chats</span>
          </span>
          <kbd className="font-mono text-[10px] text-stone-400">Ctrl+K</kbd>
        </button>
      </div>

      {/* Chronological Thread List */}
      <div className="flex-1 overflow-y-auto px-2.5 py-2 space-y-4">
        {groups.length === 0 ? (
          <div className="px-2 py-10 text-center text-xs text-stone-400 dark:text-stone-500">
            No conversations yet. Start a chat or press the mic to talk.
          </div>
        ) : (
          groups.map((group) => (
            <div key={group.label}>
              <div className="px-2 pb-1 text-[10px] font-mono uppercase tracking-wider text-stone-400 dark:text-stone-500">
                {group.label}
              </div>
              <div className="space-y-0.5">
                {group.items.map((conv) => {
                  const isActive = conv.id === activeId
                  const isEditing = editingId === conv.id
                  return (
                    <div
                      key={conv.id}
                      onClick={() => {
                        if (!isEditing) onSelectConversation(conv.id)
                      }}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !isEditing) {
                          onSelectConversation(conv.id)
                        }
                      }}
                      className={`group relative flex items-center justify-between gap-1.5 rounded-xl px-2.5 py-2 text-xs transition cursor-pointer focus-ring ${
                        isActive
                          ? 'bg-white dark:bg-stone-900 text-stone-950 dark:text-white font-semibold shadow-2xs border border-black/[0.06] dark:border-white/[0.08]'
                          : 'text-stone-600 dark:text-stone-400 hover:bg-black/[0.04] dark:hover:bg-white/[0.05] hover:text-stone-900 dark:hover:text-stone-100 border border-transparent'
                      }`}
                    >
                      {isEditing ? (
                        <div
                          className="flex items-center gap-1 flex-1 min-w-0"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="text"
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onBlur={() => commitRename(conv.id)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') commitRename(conv.id)
                              if (e.key === 'Escape') setEditingId(null)
                            }}
                            autoFocus
                            className="w-full rounded-md bg-stone-50 dark:bg-stone-950 border border-quince-400 px-1.5 py-0.5 text-xs text-stone-950 dark:text-white focus:outline-none"
                          />
                          <button
                            type="button"
                            onClick={() => commitRename(conv.id)}
                            className="p-0.5 text-quince-leaf-dark dark:text-quince-leaf"
                            aria-label="Save title"
                          >
                            <Check className="h-3 w-3" />
                          </button>
                        </div>
                      ) : (
                        <>
                          <span className="truncate flex-1">{conv.title}</span>
                          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity shrink-0">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                onTogglePin(conv.id)
                              }}
                              className="p-1 rounded-md text-stone-400 hover:text-quince-500 hover:bg-black/[0.04] dark:hover:bg-white/[0.06]"
                              title={conv.pinned ? 'Unpin' : 'Pin'}
                              aria-label={conv.pinned ? 'Unpin chat' : 'Pin chat'}
                            >
                              {conv.pinned ? (
                                <PinOff className="h-3 w-3" />
                              ) : (
                                <Pin className="h-3 w-3" />
                              )}
                            </button>
                            <button
                              type="button"
                              onClick={(e) => startRename(e, conv)}
                              className="p-1 rounded-md text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 hover:bg-black/[0.04] dark:hover:bg-white/[0.06]"
                              title="Rename"
                              aria-label="Rename chat"
                            >
                              <Pencil className="h-3 w-3" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                onDelete(conv.id)
                              }}
                              className="p-1 rounded-md text-stone-400 hover:text-rose-500 hover:bg-rose-500/10"
                              title="Delete"
                              aria-label="Delete chat"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Bottom Runtime Status & Settings Footer */}
      <div className="p-2.5 border-t border-black/[0.06] dark:border-white/[0.07] shrink-0">
        <button
          type="button"
          onClick={onOpenSettings}
          className="btn-interactive focus-ring w-full flex items-center justify-between gap-2 rounded-xl px-2.5 py-2 text-xs text-stone-600 dark:text-stone-300 hover:bg-black/[0.04] dark:hover:bg-white/[0.05] transition"
        >
          <div className="flex items-center gap-2 min-w-0">
            <span
              className={`h-2 w-2 rounded-full shrink-0 ${
                telemetry.basketReachable ? 'bg-quince-leaf' : 'bg-stone-400'
              }`}
            />
            <span className="truncate font-mono text-[11px]">
              {telemetry.activeModel || 'Basket Local LLM'}
            </span>
          </div>
          <Settings className="h-3.5 w-3.5 shrink-0 text-stone-400" />
        </button>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop docked rail */}
      <aside
        className={`hidden lg:block h-full shrink-0 transition-[width,opacity] duration-200 ease-out overflow-hidden ${
          open ? 'w-64 opacity-100' : 'w-0 opacity-0'
        }`}
        aria-label="Conversation history"
      >
        {railContent}
      </aside>

      {/* Mobile slide-over drawer */}
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-stone-950/35 backdrop-blur-xs"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          <aside
            className="relative z-10 h-full shadow-glass"
            aria-label="Mobile conversation history"
          >
            {railContent}
          </aside>
        </div>
      )}
    </>
  )
}
