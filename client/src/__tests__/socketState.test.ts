import { describe, it, expect, vi } from 'vitest'
import {
  INITIAL_TURN_STATE,
  turnRuntimeReducer,
} from '../api/basketSocketState'
import { resolveEndpointConfig } from '../api/config'
import { fetchTtsAudio } from '../api/basket'

describe('resolveEndpointConfig', () => {
  it('uses HTTPS/WSS .jam gateways when hosted on https://quince.jam', () => {
    const cfg = resolveEndpointConfig({}, { protocol: 'https:', hostname: 'quince.jam' })
    expect(cfg).toEqual({
      basketApiUrl: 'https://api.basket.jam',
      basketWsUrl: 'wss://api.basket.jam/ws',
      quinceApiUrl: 'https://api.quince.jam',
    })
  })

  it('uses local loopback ports during plain HTTP vite dev', () => {
    const cfg = resolveEndpointConfig({}, { protocol: 'http:', hostname: '127.0.0.1' })
    expect(cfg).toEqual({
      basketApiUrl: 'http://127.0.0.1:10010',
      basketWsUrl: 'ws://127.0.0.1:10010/ws',
      quinceApiUrl: 'http://127.0.0.5:10000',
    })
  })
})

describe('fetchTtsAudio', () => {
  it('strictly sends voice jane to Basket /tts/synthesize and surfaces errors without browser fallback', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/wav' }),
    })
    const origFetch = globalThis.fetch
    globalThis.fetch = fetchMock as unknown as typeof fetch

    try {
      const res = await fetchTtsAudio('Hello Quince', 'other_voice')
      expect(res.blob).not.toBeNull()
      expect(fetchMock).toHaveBeenCalledTimes(1)
      const [url, init] = fetchMock.mock.calls[0]
      expect(String(url)).toContain('/tts/synthesize')
      expect(JSON.parse(String(init.body))).toEqual({
        text: 'Hello Quince',
        voice: 'jane',
        temperature: 0.5,
        stream: false,
      })

      fetchMock.mockResolvedValueOnce({ ok: false, status: 502 })
      const failRes = await fetchTtsAudio('Fail test')
      expect(failRes.blob).toBeNull()
      expect(failRes.error).toContain('HTTP 502')
    } finally {
      globalThis.fetch = origFetch
    }
  })
})

describe('turnRuntimeReducer', () => {
  it('keeps turn active across multiple rtsi.speak + tts bursts until pipeline.completed', () => {
    let state = turnRuntimeReducer(INITIAL_TURN_STATE, {
      type: 'begin_turn',
      conversationId: 'chat_1',
      assistantMessageId: 'msg_1',
      mode: 'text',
    })
    expect(state.phase).toBe('thinking')

    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'rtsi.session', data: { active: true } },
    })
    expect(state.phase).toBe('rtsi')
    expect(state.rtsiActive).toBe(true)

    // First spoken burst must NOT reset turn to idle on tts.completed
    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'rtsi.speak', data: 'Opening Amazon now' },
    })
    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'tts.started', data: 'Opening Amazon now' },
    })
    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'tts.completed', data: 'Opening Amazon now' },
    })

    expect(state.phase).toBe('rtsi')
    expect(state.spokenPhrases).toEqual(['Opening Amazon now'])
    expect(state.rtsiSteps.length).toBeGreaterThanOrEqual(2)

    // Second burst + final reply tokens
    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'rtsi.speak', data: 'Searching for keyboards' },
    })
    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'tts.completed', data: 'Searching for keyboards' },
    })
    expect(state.phase).toBe('rtsi')

    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'rtsi.session', data: { active: false } },
    })
    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'llm.token', data: 'Found 5 keyboards ' },
    })
    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'llm.final', data: 'Found 5 keyboards under $100.' },
    })
    expect(state.assistantBuffer).toBe('Found 5 keyboards under $100.')
    expect(state.phase).toBe('thinking')

    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'pipeline.completed', data: { mode: 'text_to_voice' } },
    })
    expect(state.phase).toBe('idle')
    expect(state.rtsiActive).toBe(false)
  })

  it('handles rtsi.await_user prompt and resolution without cancelling the turn', () => {
    let state = turnRuntimeReducer(INITIAL_TURN_STATE, {
      type: 'begin_turn',
      conversationId: 'chat_2',
      assistantMessageId: 'msg_2',
      mode: 'voice',
    })

    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: {
        type: 'rtsi.await_user',
        data: { kind: 'confirmation', question: 'Submit payment for $42?', timeout_s: 60 },
      },
    })

    expect(state.phase).toBe('awaiting_user')
    expect(state.awaitUser?.kind).toBe('confirmation')
    expect(state.awaitUser?.status).toBe('pending')

    state = turnRuntimeReducer(state, {
      type: 'mark_await_user_answered',
      answer: 'yes',
    })

    expect(state.phase).toBe('rtsi')
    expect(state.awaitUser?.status).toBe('answered')
    expect(state.awaitUser?.answer).toBe('yes')
  })

  it('handles barge-in local_cancel and ws error cleanly', () => {
    let state = turnRuntimeReducer(INITIAL_TURN_STATE, {
      type: 'begin_turn',
      conversationId: 'chat_3',
      assistantMessageId: 'msg_3',
      mode: 'text',
    })
    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: { type: 'llm.token', data: 'Partial output' },
    })
    state = turnRuntimeReducer(state, { type: 'local_cancel' })
    expect(state.phase).toBe('idle')
    expect(state.assistantBuffer).toBe('Partial output')

    state = turnRuntimeReducer(state, {
      type: 'ws_event',
      event: {
        type: 'error',
        data: { code: 'llm_failed', message: 'Model timed out' },
      },
    })
    expect(state.phase).toBe('idle')
    expect(state.lastError).toEqual({ code: 'llm_failed', message: 'Model timed out' })
  })
})
