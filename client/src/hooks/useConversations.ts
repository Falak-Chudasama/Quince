import { useState, useCallback, useMemo, useEffect } from 'react'
import { ChatMessage, Conversation, ConversationGroup } from '../types/chat'
import { createId, deriveConversationTitle } from '../lib/utils'

const CONVERSATIONS_STORAGE_KEY = 'quince_conversations_v1'
const ACTIVE_ID_STORAGE_KEY = 'quince_active_conversation_v1'

function loadStoredConversations(): Conversation[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(CONVERSATIONS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((c): c is Conversation => typeof c?.id === 'string' && Array.isArray(c?.messages))
      .map((c) => ({
        ...c,
        messages: c.messages.map((m) => ({ ...m, isStreaming: false })),
      }))
  } catch {
    return []
  }
}

function loadStoredActiveId(conversations: Conversation[]): string | null {
  if (typeof window === 'undefined') return null
  try {
    const id = window.localStorage.getItem(ACTIVE_ID_STORAGE_KEY)
    if (id && conversations.some((c) => c.id === id)) return id
  } catch {
    // ignore
  }
  return conversations[0]?.id ?? null
}

export function groupConversations(
  conversations: Conversation[],
  now = Date.now(),
): ConversationGroup[] {
  const startOfToday = new Date(now)
  startOfToday.setHours(0, 0, 0, 0)
  const todayMs = startOfToday.getTime()
  const yesterdayMs = todayMs - 86_400_000
  const sevenDaysMs = todayMs - 7 * 86_400_000

  const pinned: Conversation[] = []
  const today: Conversation[] = []
  const yesterday: Conversation[] = []
  const previous7Days: Conversation[] = []
  const older: Conversation[] = []

  const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt)

  for (const conv of sorted) {
    if (conv.pinned) {
      pinned.push(conv)
    } else if (conv.updatedAt >= todayMs) {
      today.push(conv)
    } else if (conv.updatedAt >= yesterdayMs) {
      yesterday.push(conv)
    } else if (conv.updatedAt >= sevenDaysMs) {
      previous7Days.push(conv)
    } else {
      older.push(conv)
    }
  }

  const groups: ConversationGroup[] = []
  if (pinned.length > 0) groups.push({ label: 'Pinned', items: pinned })
  if (today.length > 0) groups.push({ label: 'Today', items: today })
  if (yesterday.length > 0) groups.push({ label: 'Yesterday', items: yesterday })
  if (previous7Days.length > 0) groups.push({ label: 'Previous 7 Days', items: previous7Days })
  if (older.length > 0) groups.push({ label: 'Older', items: older })
  return groups
}

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>(loadStoredConversations)
  const [activeId, setActiveId] = useState<string | null>(() =>
    loadStoredActiveId(loadStoredConversations()),
  )

  useEffect(() => {
    try {
      window.localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(conversations))
    } catch {
      // ignore storage quota errors
    }
  }, [conversations])

  useEffect(() => {
    try {
      if (activeId) {
        window.localStorage.setItem(ACTIVE_ID_STORAGE_KEY, activeId)
      } else {
        window.localStorage.removeItem(ACTIVE_ID_STORAGE_KEY)
      }
    } catch {
      // ignore
    }
  }, [activeId])

  const activeConversation = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? null,
    [conversations, activeId],
  )

  const groupedConversations = useMemo(
    () => groupConversations(conversations),
    [conversations],
  )

  const createConversation = useCallback((initialTitle = 'New Chat'): Conversation => {
    const now = Date.now()
    const created: Conversation = {
      id: createId('chat'),
      title: initialTitle,
      pinned: false,
      createdAt: now,
      updatedAt: now,
      messages: [],
    }
    setConversations((prev) => [created, ...prev])
    setActiveId(created.id)
    return created
  }, [])

  const startNewDraft = useCallback(() => {
    setActiveId(null)
  }, [])

  const ensureConversation = useCallback(
    (seedPrompt?: string): Conversation => {
      if (activeId) {
        const existing = conversations.find((c) => c.id === activeId)
        if (existing) return existing
      }
      const title = seedPrompt ? deriveConversationTitle(seedPrompt) : 'New Chat'
      return createConversation(title)
    },
    [activeId, conversations, createConversation],
  )

  const appendMessage = useCallback((conversationId: string, message: ChatMessage) => {
    setConversations((prev) =>
      prev.map((conv) => {
        if (conv.id !== conversationId) return conv
        const isFirstUserMsg =
          conv.messages.length === 0 && message.role === 'user' && conv.title === 'New Chat'
        return {
          ...conv,
          title: isFirstUserMsg ? deriveConversationTitle(message.content) : conv.title,
          updatedAt: Date.now(),
          messages: [...conv.messages, message],
        }
      }),
    )
  }, [])

  const updateMessage = useCallback(
    (
      conversationId: string,
      messageId: string,
      updater: (msg: ChatMessage) => ChatMessage,
    ) => {
      setConversations((prev) =>
        prev.map((conv) => {
          if (conv.id !== conversationId) return conv
          let touched = false
          const nextMessages = conv.messages.map((msg) => {
            if (msg.id !== messageId) return msg
            touched = true
            return updater(msg)
          })
          return touched
            ? { ...conv, updatedAt: Date.now(), messages: nextMessages }
            : conv
        }),
      )
    },
    [],
  )

  const truncateFromMessage = useCallback((conversationId: string, messageId: string) => {
    setConversations((prev) =>
      prev.map((conv) => {
        if (conv.id !== conversationId) return conv
        const idx = conv.messages.findIndex((m) => m.id === messageId)
        if (idx === -1) return conv
        return {
          ...conv,
          updatedAt: Date.now(),
          messages: conv.messages.slice(0, idx),
        }
      }),
    )
  }, [])

  const renameConversation = useCallback((conversationId: string, title: string) => {
    const trimmed = title.trim()
    if (!trimmed) return
    setConversations((prev) =>
      prev.map((conv) =>
        conv.id === conversationId ? { ...conv, title: trimmed } : conv,
      ),
    )
  }, [])

  const togglePinConversation = useCallback((conversationId: string) => {
    setConversations((prev) =>
      prev.map((conv) =>
        conv.id === conversationId ? { ...conv, pinned: !conv.pinned } : conv,
      ),
    )
  }, [])

  const deleteConversation = useCallback(
    (conversationId: string) => {
      setConversations((prev) => prev.filter((c) => c.id !== conversationId))
      setActiveId((prevActive) => {
        if (prevActive !== conversationId) return prevActive
        const remaining = conversations.filter((c) => c.id !== conversationId)
        return remaining[0]?.id ?? null
      })
    },
    [conversations],
  )

  return {
    conversations,
    groupedConversations,
    activeId,
    activeConversation,
    setActiveId,
    startNewDraft,
    createConversation,
    ensureConversation,
    appendMessage,
    updateMessage,
    truncateFromMessage,
    renameConversation,
    togglePinConversation,
    deleteConversation,
  }
}
