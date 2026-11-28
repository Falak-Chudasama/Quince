import { useState, useEffect, useRef, useReducer, useCallback } from 'react'
import {
  BasketSettings,
  ChatMessage,
  SocketConnectionState,
} from '../types/chat'
import { BASKET_WS_URL } from '../api/config'
import { streamTextChatSse } from '../api/basket'
import {
  MicCaptureController,
  PcmStreamPlayer,
  startMicCapture,
} from '../api/audio'
import {
  INITIAL_TURN_STATE,
  IncomingBasketEvent,
  turnRuntimeReducer,
} from '../api/basketSocketState'
import { createId } from '../lib/utils'

interface UseBasketSocketOptions {
  onAppendMessage: (conversationId: string, message: ChatMessage) => void
  onUpdateMessage: (
    conversationId: string,
    messageId: string,
    updater: (msg: ChatMessage) => ChatMessage,
  ) => void
  onNotifyError?: (message: string) => void
  onTurnCompleted?: () => void
  onErrorSound?: () => void
}

export function useBasketSocket({
  onAppendMessage,
  onUpdateMessage,
  onNotifyError,
  onTurnCompleted,
  onErrorSound,
}: UseBasketSocketOptions) {
  const [connectionState, setConnectionState] =
    useState<SocketConnectionState>('connecting')
  const [turnState, dispatch] = useReducer(turnRuntimeReducer, INITIAL_TURN_STATE)
  const [micLevel, setMicLevel] = useState(0)
  const [isRecording, setIsRecording] = useState(false)

  // Keep latest callbacks in a ref so connect/useEffect never tear down the WS on re-render.
  const callbacksRef = useRef<UseBasketSocketOptions>({
    onAppendMessage,
    onUpdateMessage,
    onNotifyError,
    onTurnCompleted,
    onErrorSound,
  })
  callbacksRef.current = {
    onAppendMessage,
    onUpdateMessage,
    onNotifyError,
    onTurnCompleted,
    onErrorSound,
  }

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptRef = useRef(0)
  const reconnectTimerRef = useRef<number | null>(null)
  const pingTimerRef = useRef<number | null>(null)
  const micRef = useRef<MicCaptureController | null>(null)
  const sseAbortRef = useRef<AbortController | null>(null)
  const playerRef = useRef<PcmStreamPlayer | null>(null)
  const turnStateRef = useRef(turnState)
  const voiceTurnTargetRef = useRef<{
    conversationId: string
    userMessageId: string | null
    assistantMessageId: string
    awaitingReply: boolean
  } | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    turnStateRef.current = turnState
  }, [turnState])

  if (!playerRef.current && typeof window !== 'undefined') {
    playerRef.current = new PcmStreamPlayer()
  }

  const syncAssistantMessage = useCallback(
    (next: ReturnType<typeof turnRuntimeReducer>, streaming: boolean, error?: string) => {
      if (!next.activeConversationId || !next.activeAssistantMessageId) return
      callbacksRef.current.onUpdateMessage(
        next.activeConversationId,
        next.activeAssistantMessageId,
        (msg) => ({
          ...msg,
          content: next.assistantBuffer || msg.content,
          isStreaming: streaming,
          error: error ?? msg.error,
          rtsiSteps: next.rtsiSteps,
          spokenPhrases: next.spokenPhrases,
          awaitUser: next.awaitUser ?? msg.awaitUser,
        }),
      )
    },
    [],
  )

  const handleParsedEvent = useCallback(
    (evt: IncomingBasketEvent) => {
      const prev = turnStateRef.current
      const next = turnRuntimeReducer(prev, { type: 'ws_event', event: evt })
      turnStateRef.current = next
      dispatch({ type: 'ws_event', event: evt })

      if (evt.type === 'stt.final' && typeof evt.data === 'string' && evt.data.trim()) {
        const target = voiceTurnTargetRef.current
        if (target && !target.awaitingReply && target.userMessageId) {
          const transcript = evt.data.trim()
          callbacksRef.current.onUpdateMessage(
            target.conversationId,
            target.userMessageId,
            (m) => ({
              ...m,
              content: transcript,
            }),
          )
        }
      }

      if (
        evt.type === 'rtsi.session' ||
        evt.type === 'rtsi.speak' ||
        evt.type === 'rtsi.await_user' ||
        evt.type === 'llm.token' ||
        evt.type === 'llm.final' ||
        evt.type === 'rtsi.ended'
      ) {
        syncAssistantMessage(next, true)
      } else if (evt.type === 'pipeline.completed') {
        syncAssistantMessage(next, false)
        voiceTurnTargetRef.current = null
        callbacksRef.current.onTurnCompleted?.()
      } else if (evt.type === 'cancelled') {
        syncAssistantMessage(next, false)
        voiceTurnTargetRef.current = null
      } else if (evt.type === 'error') {
        const errMsg = next.lastError?.message || 'Basket WebSocket error'
        syncAssistantMessage(next, false, errMsg)
        voiceTurnTargetRef.current = null
        callbacksRef.current.onNotifyError?.(errMsg)
        callbacksRef.current.onErrorSound?.()
      }
    },
    [syncAssistantMessage],
  )

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return
    }

    setConnectionState(reconnectAttemptRef.current > 0 ? 'reconnecting' : 'connecting')

    try {
      const ws = new WebSocket(BASKET_WS_URL)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onopen = () => {
        if (!mountedRef.current || wsRef.current !== ws) return
        reconnectAttemptRef.current = 0
        setConnectionState('connected')
        if (pingTimerRef.current) window.clearInterval(pingTimerRef.current)
        pingTimerRef.current = window.setInterval(() => {
          if (wsRef.current === ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, 25000)
      }

      ws.onmessage = async (event: MessageEvent) => {
        if (!mountedRef.current || wsRef.current !== ws) return
        if (event.data instanceof ArrayBuffer) {
          playerRef.current?.enqueuePcm16(event.data)
          return
        }
        if (typeof Blob !== 'undefined' && event.data instanceof Blob) {
          const buf = await event.data.arrayBuffer()
          if (!mountedRef.current || wsRef.current !== ws) return
          playerRef.current?.enqueuePcm16(buf)
          return
        }
        if (typeof event.data === 'string') {
          try {
            const parsed = JSON.parse(event.data) as IncomingBasketEvent
            handleParsedEvent(parsed)
          } catch {
            // ignore non-JSON frame
          }
        }
      }

      ws.onerror = () => {
        if (!mountedRef.current || wsRef.current !== ws) return
        // onclose handles backoff state transitions
      }

      ws.onclose = () => {
        if (!mountedRef.current || wsRef.current !== ws) return
        if (pingTimerRef.current) {
          window.clearInterval(pingTimerRef.current)
          pingTimerRef.current = null
        }
        wsRef.current = null
        const attempt = reconnectAttemptRef.current + 1
        reconnectAttemptRef.current = attempt
        setConnectionState(attempt <= 1 ? 'reconnecting' : 'disconnected')
        const delayMs = Math.min(12000, 600 * Math.pow(1.75, Math.min(attempt - 1, 6)))
        reconnectTimerRef.current = window.setTimeout(() => {
          connect()
        }, delayMs)
      }
    } catch {
      setConnectionState('disconnected')
    }
  }, [handleParsedEvent])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (pingTimerRef.current) {
        window.clearInterval(pingTimerRef.current)
        pingTimerRef.current = null
      }
      micRef.current?.stop()
      sseAbortRef.current?.abort()
      const activeWs = wsRef.current
      wsRef.current = null
      activeWs?.close()
      playerRef.current?.dispose()
    }
  }, [connect])

  const sendText = useCallback(
    async (
      text: string,
      conversationId: string,
      history: ChatMessage[],
      settings: BasketSettings,
    ) => {
      const trimmed = text.trim()
      if (!trimmed) return

      if (turnStateRef.current.phase === 'awaiting_user') {
        const ws = wsRef.current
        dispatch({ type: 'mark_await_user_answered', answer: trimmed })
        if (
          turnStateRef.current.activeAssistantMessageId &&
          turnStateRef.current.activeConversationId
        ) {
          callbacksRef.current.onUpdateMessage(
            turnStateRef.current.activeConversationId,
            turnStateRef.current.activeAssistantMessageId,
            (m) => ({
              ...m,
              awaitUser: m.awaitUser
                ? { ...m.awaitUser, status: 'answered', answer: trimmed }
                : undefined,
            }),
          )
        }
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'await_user_response', answer: trimmed }))
        }
        return
      }

      const userMsg: ChatMessage = {
        id: createId('msg'),
        role: 'user',
        content: trimmed,
        createdAt: Date.now(),
      }
      const assistantId = createId('msg')
      const assistantPlaceholder: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        createdAt: Date.now(),
        isStreaming: true,
        rtsiSteps: [],
        spokenPhrases: [],
        metadata: { model: settings.model || undefined },
      }

      callbacksRef.current.onAppendMessage(conversationId, userMsg)
      callbacksRef.current.onAppendMessage(conversationId, assistantPlaceholder)

      const beginAction = {
        type: 'begin_turn' as const,
        conversationId,
        assistantMessageId: assistantId,
        mode: 'text' as const,
      }
      turnStateRef.current = turnRuntimeReducer(turnStateRef.current, beginAction)
      dispatch(beginAction)

      const llmMessages = history.slice(-16).map((m) => ({
        role: m.role,
        content: m.content,
      }))

      const requestPayload = {
        type: 'text_input',
        application: 'quince',
        text: trimmed,
        synthesize_speech: settings.synthesizeSpeech,
        chat_id: conversationId,
        retrieve_chat: settings.retrieveChat,
        retrieve_notes: settings.retrieveNotes,
        llm: {
          model: settings.model || undefined,
          messages: llmMessages,
          temperature: settings.temperature,
          max_tokens: settings.maxTokens,
          abstracted: true,
        },
        tts: {
          voice: settings.voice || undefined,
        },
      }

      const ws = wsRef.current
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(requestPayload))
        return
      }

      // Fallback to Basket HTTP SSE /chat/text if WebSocket isn't open
      const abort = new AbortController()
      sseAbortRef.current = abort
      try {
        await streamTextChatSse(
          requestPayload,
          {
            onDelta: (token) => handleParsedEvent({ type: 'llm.token', data: token }),
            onFinal: (finalText) => handleParsedEvent({ type: 'llm.final', data: finalText }),
            onDone: () => handleParsedEvent({ type: 'pipeline.completed' }),
            onError: (message) =>
              handleParsedEvent({ type: 'error', data: { code: 'sse_error', message } }),
          },
          abort.signal,
        )
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') {
          handleParsedEvent({ type: 'cancelled' })
          return
        }
        const msg =
          err instanceof Error
            ? `Basket unreachable (${msgOrFallback(err.message)}).`
            : 'Basket server is currently unreachable.'
        handleParsedEvent({ type: 'error', data: { code: 'offline', message: msg } })
      } finally {
        if (sseAbortRef.current === abort) {
          sseAbortRef.current = null
        }
      }
    },
    [handleParsedEvent],
  )

  const sendAwaitUserAnswer = useCallback((answer: string) => {
    const trimmed = answer.trim()
    if (!trimmed) return
    const current = turnStateRef.current
    dispatch({ type: 'mark_await_user_answered', answer: trimmed })
    if (current.activeConversationId && current.activeAssistantMessageId) {
      callbacksRef.current.onUpdateMessage(
        current.activeConversationId,
        current.activeAssistantMessageId,
        (m) => ({
          ...m,
          awaitUser: m.awaitUser
            ? { ...m.awaitUser, status: 'answered', answer: trimmed }
            : undefined,
        }),
      )
    }
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'await_user_response', answer: trimmed }))
    } else {
      callbacksRef.current.onNotifyError?.('WebSocket disconnected before sending approval.')
    }
  }, [])

  const startVoice = useCallback(
    async (
      conversationId: string,
      history: ChatMessage[],
      settings: BasketSettings,
    ) => {
      const ws = wsRef.current
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        callbacksRef.current.onNotifyError?.(
          'Connect to Basket WebSocket to use live voice streaming.',
        )
        callbacksRef.current.onErrorSound?.()
        return
      }

      const awaitingUser = turnStateRef.current.phase === 'awaiting_user'
      playerRef.current?.stopAll()

      let userMessageId: string | null = null
      let assistantMessageId = turnStateRef.current.activeAssistantMessageId || createId('msg')

      if (!awaitingUser) {
        userMessageId = createId('msg')
        assistantMessageId = createId('msg')
        callbacksRef.current.onAppendMessage(conversationId, {
          id: userMessageId,
          role: 'user',
          content: 'Listening...',
          createdAt: Date.now(),
          metadata: { fromVoice: true },
        })
        callbacksRef.current.onAppendMessage(conversationId, {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          createdAt: Date.now(),
          isStreaming: true,
          rtsiSteps: [],
          spokenPhrases: [],
          metadata: { model: settings.model || undefined },
        })

        const beginAction = {
          type: 'begin_turn' as const,
          conversationId,
          assistantMessageId,
          mode: 'voice' as const,
        }
        turnStateRef.current = turnRuntimeReducer(turnStateRef.current, beginAction)
        dispatch(beginAction)
      }

      voiceTurnTargetRef.current = {
        conversationId,
        userMessageId,
        assistantMessageId,
        awaitingReply: awaitingUser,
      }

      try {
        ws.send(
          JSON.stringify({
            type: 'start',
            application: 'quince',
            stream: true,
            sample_rate: 16000,
            chat_id: conversationId,
            retrieve_chat: settings.retrieveChat,
            retrieve_notes: settings.retrieveNotes,
            llm: {
              model: settings.model || undefined,
              messages: history.slice(-16).map((m) => ({
                role: m.role,
                content: m.content,
              })),
              temperature: settings.temperature,
              max_tokens: settings.maxTokens,
              abstracted: true,
            },
            tts: {
              voice: settings.voice || undefined,
            },
          }),
        )

        const controller = await startMicCapture(
          (chunk) => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(chunk)
            }
          },
          (level) => setMicLevel(level),
        )
        micRef.current = controller
        setIsRecording(true)
      } catch (err) {
        setIsRecording(false)
        setMicLevel(0)
        callbacksRef.current.onNotifyError?.(
          err instanceof Error ? err.message : 'Unable to access microphone.',
        )
        callbacksRef.current.onErrorSound?.()
      }
    },
    [],
  )

  const stopVoice = useCallback(() => {
    micRef.current?.stop()
    micRef.current = null
    setIsRecording(false)
    setMicLevel(0)
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'stop' }))
    }
  }, [])

  const cancelTurn = useCallback(() => {
    micRef.current?.stop()
    micRef.current = null
    setIsRecording(false)
    setMicLevel(0)
    playerRef.current?.stopAll()
    sseAbortRef.current?.abort()
    sseAbortRef.current = null

    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'cancel' }))
    }

    const prev = turnStateRef.current
    const next = turnRuntimeReducer(prev, { type: 'local_cancel' })
    turnStateRef.current = next
    dispatch({ type: 'local_cancel' })
    syncAssistantMessage(next, false)
  }, [syncAssistantMessage])

  const stopAudioPlayback = useCallback(() => {
    playerRef.current?.stopAll()
  }, [])

  const reconnectNow = useCallback(() => {
    reconnectAttemptRef.current = 0
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    const existing = wsRef.current
    if (existing && existing.readyState !== WebSocket.OPEN) {
      wsRef.current = null
      try {
        existing.close()
      } catch {
        // ignore close failure
      }
    }
    connect()
  }, [connect])

  return {
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
  }
}

function msgOrFallback(msg: string): string {
  return msg || 'network error'
}
