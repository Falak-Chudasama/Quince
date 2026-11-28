import React, { createContext, useContext, useState, useCallback } from 'react'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'
import { createId } from '../lib/utils'

export type ToastTone = 'success' | 'error' | 'info'

interface ToastItem {
  id: string
  tone: ToastTone
  message: string
}

interface ToastContextValue {
  push: (tone: ToastTone, message: string, durationMs?: number) => void
}

const ToastContext = createContext<ToastContextValue>({
  push: () => {},
})

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id))
  }, [])

  const push = useCallback(
    (tone: ToastTone, message: string, durationMs = 3600) => {
      const id = createId('toast')
      setToasts((prev) => [...prev.slice(-3), { id, tone, message }])
      window.setTimeout(() => {
        dismiss(id)
      }, durationMs)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div
        className="pointer-events-none fixed bottom-24 right-4 z-50 flex flex-col gap-2 max-w-xs w-full sm:w-auto"
        aria-live="polite"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="pointer-events-auto animate-slide-up flex items-center gap-2.5 rounded-2xl glass-panel border border-black/[0.08] dark:border-white/[0.10] px-3.5 py-2.5 text-xs shadow-glass"
          >
            {toast.tone === 'success' && (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-quince-leaf-dark dark:text-quince-leaf" />
            )}
            {toast.tone === 'error' && (
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-500" />
            )}
            {toast.tone === 'info' && (
              <Info className="h-4 w-4 shrink-0 text-quince-500 dark:text-quince-400" />
            )}
            <span className="flex-1 text-stone-800 dark:text-stone-100 leading-snug">
              {toast.message}
            </span>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              className="p-0.5 rounded-md text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 transition"
              aria-label="Dismiss notification"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
