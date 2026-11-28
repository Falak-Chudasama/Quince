import { AwaitUserPrompt, RtsiStep, TurnPhase } from '../types/chat'
import { createId } from '../lib/utils'

export interface IncomingBasketEvent {
  application?: string
  type: string
  data?: unknown
}

export interface TurnRuntimeState {
  phase: TurnPhase
  turnMode: 'text' | 'voice' | null
  rtsiActive: boolean
  activeConversationId: string | null
  activeAssistantMessageId: string | null
  transcriptPreview: string
  assistantBuffer: string
  rtsiSteps: RtsiStep[]
  spokenPhrases: string[]
  awaitUser: AwaitUserPrompt | null
  lastError: { code: string; message: string } | null
}

export const INITIAL_TURN_STATE: TurnRuntimeState = {
  phase: 'idle',
  turnMode: null,
  rtsiActive: false,
  activeConversationId: null,
  activeAssistantMessageId: null,
  transcriptPreview: '',
  assistantBuffer: '',
  rtsiSteps: [],
  spokenPhrases: [],
  awaitUser: null,
  lastError: null,
}

export type TurnAction =
  | {
      type: 'begin_turn'
      conversationId: string
      assistantMessageId: string
      mode: 'text' | 'voice'
    }
  | {
      type: 'mark_await_user_answered'
      answer: string
    }
  | {
      type: 'ws_event'
      event: IncomingBasketEvent
    }
  | {
      type: 'local_cancel'
    }

function completeRunningSteps(steps: RtsiStep[]): RtsiStep[] {
  return steps.map((step) =>
    step.status === 'running' || step.status === 'waiting'
      ? { ...step, status: 'completed' }
      : step,
  )
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

export function turnRuntimeReducer(
  state: TurnRuntimeState,
  action: TurnAction,
): TurnRuntimeState {
  switch (action.type) {
    case 'begin_turn':
      return {
        phase: action.mode === 'voice' ? 'listening' : 'thinking',
        turnMode: action.mode,
        rtsiActive: false,
        activeConversationId: action.conversationId,
        activeAssistantMessageId: action.assistantMessageId,
        transcriptPreview: '',
        assistantBuffer: '',
        rtsiSteps: [],
        spokenPhrases: [],
        awaitUser: null,
        lastError: null,
      }

    case 'mark_await_user_answered':
      return {
        ...state,
        phase: state.rtsiActive ? 'rtsi' : 'thinking',
        awaitUser: state.awaitUser
          ? { ...state.awaitUser, status: 'answered', answer: action.answer }
          : null,
        rtsiSteps: state.rtsiSteps.map((step) =>
          step.status === 'waiting'
            ? { ...step, status: 'completed', detail: `${step.detail || ''} → ${action.answer}`.trim() }
            : step,
        ),
      }

    case 'local_cancel':
      return {
        ...state,
        phase: 'idle',
        rtsiActive: false,
        awaitUser: null,
        rtsiSteps: completeRunningSteps(state.rtsiSteps),
      }

    case 'ws_event': {
      const { type, data } = action.event
      const payload = asRecord(data)

      switch (type) {
        case 'ready':
        case 'pong':
          return state

        case 'started':
        case 'pipeline.started': {
          const mode = typeof payload?.mode === 'string' ? payload.mode : undefined
          if (state.phase === 'awaiting_user') return state
          return {
            ...state,
            phase: mode === 'voice_to_voice' ? 'listening' : 'thinking',
            lastError: null,
          }
        }

        case 'stt.started':
          return {
            ...state,
            phase: 'transcribing',
          }

        case 'stt.partial':
          return {
            ...state,
            phase: 'transcribing',
            transcriptPreview:
              state.turnMode === 'voice'
                ? typeof data === 'string'
                  ? data
                  : String(payload?.text ?? '')
                : state.transcriptPreview,
          }

        case 'stt.final':
          return {
            ...state,
            phase: state.rtsiActive ? 'rtsi' : 'thinking',
            transcriptPreview:
              state.turnMode === 'voice'
                ? typeof data === 'string'
                  ? data
                  : String(payload?.text ?? '')
                : '',
          }

        case 'rtsi.session': {
          const active = payload?.active !== false
          if (active) {
            return {
              ...state,
              phase: 'rtsi',
              rtsiActive: true,
              rtsiSteps: [
                ...state.rtsiSteps,
                {
                  id: createId('step'),
                  timestamp: Date.now(),
                  kind: 'session',
                  label: 'Browser agent engaged',
                  detail: 'Inspecting page state & tools',
                  status: 'running',
                },
              ],
            }
          }
          return {
            ...state,
            rtsiActive: false,
            phase: state.phase === 'idle' ? 'idle' : 'thinking',
            awaitUser:
              state.awaitUser && state.awaitUser.status === 'pending'
                ? { ...state.awaitUser, status: 'answered' }
                : state.awaitUser,
            rtsiSteps: completeRunningSteps(state.rtsiSteps),
          }
        }

        case 'rtsi.ended':
          return {
            ...state,
            rtsiActive: false,
            phase: state.phase === 'idle' ? 'idle' : 'thinking',
            rtsiSteps: completeRunningSteps(state.rtsiSteps),
          }

        case 'rtsi.speak': {
          const phrase =
            typeof data === 'string'
              ? data.trim()
              : String(payload?.text ?? payload?.speak ?? '').trim()
          if (!phrase) return state
          return {
            ...state,
            phase: state.rtsiActive ? 'rtsi' : 'speaking',
            spokenPhrases: [...state.spokenPhrases, phrase],
            rtsiSteps: [
              ...state.rtsiSteps,
              {
                id: createId('step'),
                timestamp: Date.now(),
                kind: 'speak',
                label: 'Voice status',
                detail: phrase,
                status: 'completed',
              },
            ],
          }
        }

        case 'rtsi.await_user': {
          const kind = typeof payload?.kind === 'string' ? payload.kind : 'confirmation'
          const question =
            typeof payload?.question === 'string'
              ? payload.question
              : typeof data === 'string'
                ? data
                : 'Confirmation needed to continue.'
          const timeout_s =
            typeof payload?.timeout_s === 'number' ? payload.timeout_s : 60
          return {
            ...state,
            phase: 'awaiting_user',
            rtsiActive: true,
            awaitUser: {
              id: createId('await'),
              kind,
              question,
              timeout_s,
              status: 'pending',
            },
            rtsiSteps: [
              ...state.rtsiSteps,
              {
                id: createId('step'),
                timestamp: Date.now(),
                kind: 'await_user',
                label: kind === 'confirmation' ? 'Approval required' : 'Question for you',
                detail: question,
                status: 'waiting',
              },
            ],
          }
        }

        case 'llm.token': {
          const delta = typeof data === 'string' ? data : ''
          return {
            ...state,
            phase: state.rtsiActive ? 'rtsi' : 'thinking',
            assistantBuffer: `${state.assistantBuffer}${delta}`,
          }
        }

        case 'llm.final': {
          const finalText = typeof data === 'string' ? data : state.assistantBuffer
          return {
            ...state,
            assistantBuffer: finalText,
          }
        }

        case 'tts.started':
          // Stay in RTSI or awaiting_user if RTSI loop is still running; otherwise mark speaking.
          return {
            ...state,
            phase:
              state.phase === 'rtsi' || state.phase === 'awaiting_user'
                ? state.phase
                : 'speaking',
          }

        case 'tts.completed':
          // Never prematurely reset the turn to idle on tts.completed!
          // Multi-burst RTSI turns emit several tts.started/tts.completed cycles
          // before pipeline.completed finally ends the turn.
          return state

        case 'pipeline.completed':
          return {
            ...state,
            phase: 'idle',
            rtsiActive: false,
            transcriptPreview: '',
            awaitUser:
              state.awaitUser && state.awaitUser.status === 'pending'
                ? { ...state.awaitUser, status: 'answered' }
                : state.awaitUser,
            rtsiSteps: completeRunningSteps(state.rtsiSteps),
          }

        case 'cancelled':
          return {
            ...state,
            phase: 'idle',
            rtsiActive: false,
            transcriptPreview: '',
            awaitUser: null,
            rtsiSteps: completeRunningSteps(state.rtsiSteps),
          }

        case 'error': {
          const code = typeof payload?.code === 'string' ? payload.code : 'ws_error'
          const message =
            typeof payload?.message === 'string'
              ? payload.message
              : typeof data === 'string'
                ? data
                : 'An unexpected error occurred.'
          return {
            ...state,
            phase: 'idle',
            rtsiActive: false,
            transcriptPreview: '',
            awaitUser: null,
            rtsiSteps: state.rtsiSteps.map((s) =>
              s.status === 'running' || s.status === 'waiting'
                ? { ...s, status: 'error' }
                : s,
            ),
            lastError: { code, message },
          }
        }

        default:
          return state
      }
    }

    default:
      return state
  }
}
