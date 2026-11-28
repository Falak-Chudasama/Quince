import React from 'react'
import { Globe, Terminal, Sparkles, BrainCircuit } from 'lucide-react'
import { QuinceLogo } from './QuinceLogo'
import { SocketConnectionState } from '../types/chat'

interface WelcomeEmptyStateProps {
  connectionState: SocketConnectionState
  activeModel: string
  onSelectPrompt: (prompt: string) => void
}

const SUGGESTIONS = [
  {
    title: 'Automate the browser',
    subtitle: 'Search Amazon for mechanical keyboards under \$100',
    prompt: 'Open Amazon in Chrome and search for wireless mechanical keyboards under $100',
    icon: Globe,
  },
  {
    title: 'Quick workspace check',
    subtitle: 'Inspect active windows & system status',
    prompt: 'Check what applications and active tasks are currently running on my desktop',
    icon: Terminal,
  },
  {
    title: 'Recall from memory',
    subtitle: 'Search my Basket notes & past context',
    prompt: 'Summarize the key decisions from our recent notes and conversations',
    icon: BrainCircuit,
  },
  {
    title: 'Draft & reason clearly',
    subtitle: 'Break down a problem with structured steps',
    prompt: 'Help me compare pros and cons of Redis Streams vs WebSockets for real-time telemetry',
    icon: Sparkles,
  },
]

export const WelcomeEmptyState: React.FC<WelcomeEmptyStateProps> = ({
  connectionState,
  activeModel,
  onSelectPrompt,
}) => {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 py-10">
      <div className="w-full max-w-2xl mx-auto flex flex-col items-center text-center">
        <div className="relative mb-5">
          <div
            className="absolute -inset-4 rounded-full bg-quince-400/20 blur-xl pointer-events-none"
            aria-hidden="true"
          />
          <div className="relative h-16 w-16 rounded-3xl surface-card shadow-soft flex items-center justify-center">
            <QuinceLogo size="lg" breathing />
          </div>
        </div>

        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-stone-950 dark:text-white">
          Quince
        </h1>
        <p className="mt-2 max-w-md text-sm text-stone-600 dark:text-stone-400 leading-relaxed">
          Voice-first desktop &amp; browser operator. Ask anything, run multi-step Chrome tasks, or talk hands-free.
        </p>

        <div className="mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1 surface-card text-[11px] font-mono text-stone-500 dark:text-stone-400">
          <span
            className={`h-2 w-2 rounded-full ${
              connectionState === 'connected'
                ? 'bg-quince-leaf'
                : connectionState === 'reconnecting' || connectionState === 'connecting'
                  ? 'bg-quince-400 animate-pulse'
                  : 'bg-stone-400'
            }`}
          />
          <span>
            {connectionState === 'connected'
              ? 'Basket Live'
              : connectionState === 'reconnecting'
                ? 'Reconnecting'
                : connectionState === 'connecting'
                  ? 'Connecting'
                  : 'Offline mode'}
          </span>
          {activeModel && (
            <>
              <span className="text-stone-300 dark:text-stone-700">·</span>
              <span className="truncate max-w-[180px] text-stone-700 dark:text-stone-300">
                {activeModel}
              </span>
            </>
          )}
        </div>

        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left">
          {SUGGESTIONS.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.title}
                type="button"
                onClick={() => onSelectPrompt(item.prompt)}
                className="btn-interactive focus-ring group rounded-2xl surface-card p-3.5 hover:border-quince-400/50 dark:hover:border-quince-400/40 hover:shadow-soft transition text-left"
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 h-7 w-7 rounded-xl bg-stone-100 dark:bg-stone-850 flex items-center justify-center shrink-0 text-stone-600 dark:text-stone-300 group-hover:bg-quince-100 dark:group-hover:bg-quince-400/15 group-hover:text-quince-600 dark:group-hover:text-quince-300 transition">
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-stone-900 dark:text-stone-100">
                      {item.title}
                    </div>
                    <div className="mt-0.5 text-xs text-stone-500 dark:text-stone-400 line-clamp-2 leading-snug">
                      {item.subtitle}
                    </div>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
