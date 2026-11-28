export type Role = 'user' | 'assistant' | 'system'

export type ThemePreference = 'light' | 'dark' | 'system'

export type SocketConnectionState =
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected'

export type TurnPhase =
  | 'idle'
  | 'listening'
  | 'transcribing'
  | 'thinking'
  | 'rtsi'
  | 'awaiting_user'
  | 'speaking'

export interface RtsiStep {
  id: string
  timestamp: number
  kind: 'session' | 'speak' | 'await_user' | 'tool' | 'info'
  label: string
  detail?: string
  status: 'running' | 'completed' | 'waiting' | 'error'
}

export interface AwaitUserPrompt {
  id: string
  kind: 'confirmation' | 'question' | string
  question: string
  timeout_s?: number
  status: 'pending' | 'answered' | 'expired'
  answer?: string
}

export interface ChatMessage {
  id: string
  role: Role
  content: string
  createdAt: number
  isStreaming?: boolean
  error?: string
  rtsiSteps?: RtsiStep[]
  awaitUser?: AwaitUserPrompt
  spokenPhrases?: string[]
  metadata?: {
    model?: string
    durationMs?: number
    fromVoice?: boolean
  }
}

export interface Conversation {
  id: string
  title: string
  pinned: boolean
  createdAt: number
  updatedAt: number
  messages: ChatMessage[]
}

export interface ConversationGroup {
  label: string
  items: Conversation[]
}

export interface BasketSettings {
  model: string
  voice: string
  retrieveChat: boolean
  retrieveNotes: boolean
  synthesizeSpeech: boolean
  temperature: number
  maxTokens: number
}

export interface TelemetrySnapshot {
  basketReachable: boolean
  quinceReachable: boolean
  availableModels: string[]
  activeModel: string
  lastCheckedAt: number
}
