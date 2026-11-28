import React, { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Globe,
  Volume2,
  ShieldAlert,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import { RtsiStep } from '../types/chat'

interface RtsiTimelineCardProps {
  steps: RtsiStep[]
  isLive?: boolean
}

export const RtsiTimelineCard: React.FC<RtsiTimelineCardProps> = ({
  steps,
  isLive = false,
}) => {
  const [expanded, setExpanded] = useState(isLive)

  if (!steps || steps.length === 0) return null

  const hasRunning = steps.some((s) => s.status === 'running')
  const hasWaiting = steps.some((s) => s.status === 'waiting')
  const hasError = steps.some((s) => s.status === 'error')
  const latest = steps[steps.length - 1]

  return (
    <div className="mb-3 rounded-2xl surface-card shadow-2xs overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full px-3.5 py-2 flex items-center justify-between gap-2 text-left hover:bg-stone-100/70 dark:hover:bg-white/[0.03] transition focus-ring"
      >
        <div className="flex items-center gap-2 min-w-0">
          {hasRunning ? (
            <Loader2 className="h-3.5 w-3.5 shrink-0 text-quince-500 dark:text-quince-400 animate-spin" />
          ) : hasWaiting ? (
            <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-quince-500 dark:text-quince-400" />
          ) : hasError ? (
            <AlertCircle className="h-3.5 w-3.5 shrink-0 text-rose-500" />
          ) : (
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-quince-leaf-dark dark:text-quince-leaf" />
          )}

          <span className="font-mono text-[11px] uppercase tracking-wider text-stone-500 dark:text-stone-400 shrink-0">
            RTSI
          </span>
          <span className="text-xs font-medium text-stone-800 dark:text-stone-200 truncate">
            {latest.detail || latest.label}
          </span>
        </div>

        <div className="flex items-center gap-2 shrink-0 text-[11px] font-mono text-stone-400 dark:text-stone-500">
          <span>
            {steps.length} {steps.length === 1 ? 'event' : 'events'}
          </span>
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-black/[0.06] dark:border-white/[0.08] px-3.5 py-2.5 space-y-2 bg-stone-50/70 dark:bg-stone-950/40">
          {steps.map((step) => (
            <div key={step.id} className="flex items-start gap-2.5 text-xs">
              <span className="mt-0.5 shrink-0">
                {step.kind === 'speak' ? (
                  <Volume2 className="h-3.5 w-3.5 text-quince-500 dark:text-quince-400" />
                ) : step.kind === 'await_user' ? (
                  <ShieldAlert className="h-3.5 w-3.5 text-quince-500 dark:text-quince-400" />
                ) : (
                  <Globe className="h-3.5 w-3.5 text-stone-500 dark:text-stone-400" />
                )}
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-stone-800 dark:text-stone-200">
                    {step.label}
                  </span>
                  <span className="font-mono text-[10px] text-stone-400 dark:text-stone-500 uppercase">
                    {step.status}
                  </span>
                </div>
                {step.detail && (
                  <p className="text-stone-600 dark:text-stone-400 leading-snug mt-0.5 break-words">
                    {step.detail}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
