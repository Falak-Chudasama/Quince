import { BASKET_API_URL, QUINCE_API_URL } from './config'
import { TelemetrySnapshot } from '../types/chat'

async function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs = 4500,
): Promise<Response> {
  const controller = new AbortController()
  const timer = globalThis.setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(url, { ...init, signal: controller.signal })
  } finally {
    globalThis.clearTimeout(timer)
  }
}

export async function fetchAvailableModels(): Promise<string[]> {
  try {
    const res = await fetchWithTimeout(`${BASKET_API_URL}/llm/models`)
    if (!res.ok) return []
    const payload = await res.json()
    if (Array.isArray(payload)) {
      return payload.map((item) =>
        typeof item === 'string' ? item : String(item?.id || item?.name || ''),
      ).filter(Boolean)
    }
    if (Array.isArray(payload?.models)) {
      return payload.models
        .map((item: unknown) =>
          typeof item === 'string'
            ? item
            : String((item as Record<string, unknown>)?.id || (item as Record<string, unknown>)?.name || ''),
        )
        .filter(Boolean)
    }
    if (Array.isArray(payload?.data)) {
      return payload.data
        .map((item: unknown) =>
          typeof item === 'string'
            ? item
            : String((item as Record<string, unknown>)?.id || (item as Record<string, unknown>)?.name || ''),
        )
        .filter(Boolean)
    }
    return []
  } catch {
    return []
  }
}

export async function fetchTelemetrySnapshot(
  currentModel: string,
): Promise<TelemetrySnapshot> {
  let basketReachable = false
  let quinceReachable = false
  let availableModels: string[] = []
  let activeModel = currentModel

  try {
    const res = await fetchWithTimeout(`${BASKET_API_URL}/llm/models`, {}, 3000)
    if (res.ok) {
      basketReachable = true
      const data = await res.json()
      const list = Array.isArray(data?.models)
        ? data.models
        : Array.isArray(data?.data)
          ? data.data
          : Array.isArray(data)
            ? data
            : []
      availableModels = list
        .map((item: unknown) =>
          typeof item === 'string'
            ? item
            : String((item as Record<string, unknown>)?.id || (item as Record<string, unknown>)?.name || ''),
        )
        .filter(Boolean)
      if (!activeModel && availableModels.length > 0) {
        activeModel = availableModels[0]
      }
      if (typeof data?.active_model === 'string' && data.active_model) {
        activeModel = data.active_model
      }
    }
  } catch {
    basketReachable = false
  }

  try {
    const res = await fetchWithTimeout(`${QUINCE_API_URL}/health`, {}, 2000)
    quinceReachable = res.ok
  } catch {
    quinceReachable = false
  }

  return {
    basketReachable,
    quinceReachable,
    availableModels,
    activeModel,
    lastCheckedAt: Date.now(),
  }
}

export interface StreamSseHandlers {
  onDelta: (token: string) => void
  onFinal: (text: string) => void
  onDone: () => void
  onError: (message: string) => void
}

export async function streamTextChatSse(
  body: Record<string, unknown>,
  handlers: StreamSseHandlers,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASKET_API_URL}/chat/text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status} from Basket /chat/text`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split(/\r?\n/)
    buffer = lines.pop() ?? ''

    for (const rawLine of lines) {
      const line = rawLine.trim()
      if (!line.startsWith('data:')) continue
      const jsonStr = line.slice(5).trim()
      if (!jsonStr || jsonStr === '[DONE]') continue
      try {
        const evt = JSON.parse(jsonStr) as { type?: string; data?: unknown }
        if (evt.type === 'llm.token' && typeof evt.data === 'string') {
          handlers.onDelta(evt.data)
        } else if (evt.type === 'llm.final' && typeof evt.data === 'string') {
          handlers.onFinal(evt.data)
        } else if (evt.type === 'error') {
          const msg =
            typeof evt.data === 'object' && evt.data && 'message' in evt.data
              ? String((evt.data as { message?: unknown }).message)
              : 'Basket chat error'
          handlers.onError(msg)
        }
      } catch {
        // ignore partial lines
      }
    }
  }
  handlers.onDone()
}

export async function fetchTtsAudio(
  text: string,
  _voice = 'jane',
  temperature = 0.5,
): Promise<{ blob: Blob | null; error?: string }> {
  const normalizedVoice = 'jane'
  try {
    const res = await fetchWithTimeout(
      `${BASKET_API_URL}/tts/synthesize`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          voice: normalizedVoice,
          temperature,
          stream: false,
        }),
      },
      30000,
    )
    if (!res.ok) {
      return { blob: null, error: `Basket TTS returned HTTP ${res.status}` }
    }
    const blob = await res.blob()
    if (!blob || blob.size === 0) {
      return { blob: null, error: 'Basket TTS returned empty audio.' }
    }
    return { blob }
  } catch (err) {
    return {
      blob: null,
      error:
        err instanceof Error
          ? `Basket TTS request failed: ${err.message}`
          : 'Basket TTS service is unreachable.',
    }
  }
}
