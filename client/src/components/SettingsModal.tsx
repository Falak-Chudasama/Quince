import React from 'react'
import { X, RefreshCw, Server, Radio, Cpu } from 'lucide-react'
import {
  BasketSettings,
  SocketConnectionState,
  TelemetrySnapshot,
} from '../types/chat'
import { BASKET_API_URL, BASKET_WS_URL, QUINCE_API_URL } from '../api/config'

interface SettingsModalProps {
  open: boolean
  settings: BasketSettings
  connectionState: SocketConnectionState
  telemetry: TelemetrySnapshot
  onClose: () => void
  onUpdateSettings: (patch: Partial<BasketSettings>) => void
  onRefreshTelemetry: () => void
  onReconnectWs: () => void
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  open,
  settings,
  connectionState,
  telemetry,
  onClose,
  onUpdateSettings,
  onRefreshTelemetry,
  onReconnectWs,
}) => {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="fixed inset-0 bg-stone-950/35 backdrop-blur-xs"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Quince settings and telemetry"
        className="relative z-10 w-full max-w-md rounded-3xl glass-panel border border-black/[0.08] dark:border-white/[0.12] shadow-glass p-5 animate-slide-up max-h-[85vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between gap-2 pb-3 border-b border-black/[0.06] dark:border-white/[0.08]">
          <h2 className="font-display text-base font-semibold text-stone-950 dark:text-white">
            Settings &amp; Telemetry
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-xl text-stone-400 hover:text-stone-800 dark:hover:text-white"
            aria-label="Close settings"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-4 space-y-4">
          {/* Runtime Health Telemetry */}
          <div className="rounded-2xl surface-card p-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-wider text-stone-500 dark:text-stone-400">
                Endpoints
              </span>
              <button
                type="button"
                onClick={() => {
                  onRefreshTelemetry()
                  onReconnectWs()
                }}
                className="btn-interactive inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium text-stone-600 dark:text-stone-300 hover:bg-black/[0.04] dark:hover:bg-white/[0.06]"
              >
                <RefreshCw className="h-3 w-3" />
                <span>Refresh</span>
              </button>
            </div>

            <div className="space-y-1.5 text-xs font-mono">
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-stone-600 dark:text-stone-300 truncate">
                  <Radio className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{BASKET_WS_URL}</span>
                </span>
                <span
                  className={
                    connectionState === 'connected'
                      ? 'text-quince-leaf-dark dark:text-quince-leaf'
                      : 'text-quince-500'
                  }
                >
                  {connectionState}
                </span>
              </div>

              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-stone-600 dark:text-stone-300 truncate">
                  <Server className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{BASKET_API_URL}</span>
                </span>
                <span
                  className={
                    telemetry.basketReachable
                      ? 'text-quince-leaf-dark dark:text-quince-leaf'
                      : 'text-stone-400'
                  }
                >
                  {telemetry.basketReachable ? 'online' : 'unreachable'}
                </span>
              </div>

              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-stone-600 dark:text-stone-300 truncate">
                  <Cpu className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{QUINCE_API_URL}</span>
                </span>
                <span
                  className={
                    telemetry.quinceReachable
                      ? 'text-quince-leaf-dark dark:text-quince-leaf'
                      : 'text-stone-400'
                  }
                >
                  {telemetry.quinceReachable ? 'online' : 'idle'}
                </span>
              </div>
            </div>
          </div>

          {/* Model Selection */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-stone-700 dark:text-stone-200">
              Active Model
            </label>
            {telemetry.availableModels.length > 0 ? (
              <select
                value={settings.model || telemetry.activeModel}
                onChange={(e) => onUpdateSettings({ model: e.target.value })}
                className="w-full rounded-xl border border-black/[0.08] dark:border-white/[0.10] bg-white dark:bg-stone-900 px-3 py-2 text-xs font-mono text-stone-900 dark:text-stone-100 focus-ring"
              >
                {telemetry.availableModels.map((modelId) => (
                  <option key={modelId} value={modelId}>
                    {modelId}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={settings.model}
                onChange={(e) => onUpdateSettings({ model: e.target.value })}
                placeholder="Default Basket server model"
                className="w-full rounded-xl border border-black/[0.08] dark:border-white/[0.10] bg-white dark:bg-stone-900 px-3 py-2 text-xs font-mono text-stone-900 dark:text-stone-100 placeholder:text-stone-400 focus-ring"
              />
            )}
          </div>

          {/* Voice & Sampling */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-stone-700 dark:text-stone-200">
                TTS Voice
              </label>
              <div className="w-full rounded-xl border border-black/[0.08] dark:border-white/[0.10] bg-stone-100/70 dark:bg-stone-900 px-3 py-2 text-xs font-mono text-stone-800 dark:text-stone-200 flex items-center justify-between">
                <span>Jane</span>
                <span className="text-[10px] uppercase text-stone-400">Pocket TTS</span>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-stone-700 dark:text-stone-200">
                Temperature ({settings.temperature.toFixed(2)})
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={settings.temperature}
                onChange={(e) =>
                  onUpdateSettings({ temperature: parseFloat(e.target.value) })
                }
                className="w-full accent-quince-400 mt-2"
              />
            </div>
          </div>

          {/* Keyboard Shortcuts */}
          <div className="rounded-2xl surface-card p-3.5 text-xs space-y-1.5">
            <div className="font-mono text-[11px] uppercase tracking-wider text-stone-500 dark:text-stone-400 pb-1">
              Shortcuts
            </div>
            <div className="flex justify-between text-stone-600 dark:text-stone-300">
              <span>Quick search</span>
              <kbd className="font-mono text-[11px]">Ctrl/Cmd + K</kbd>
            </div>
            <div className="flex justify-between text-stone-600 dark:text-stone-300">
              <span>New chat</span>
              <kbd className="font-mono text-[11px]">Ctrl/Cmd + Shift + O</kbd>
            </div>
            <div className="flex justify-between text-stone-600 dark:text-stone-300">
              <span>Toggle sidebar</span>
              <kbd className="font-mono text-[11px]">Ctrl/Cmd + B</kbd>
            </div>
            <div className="flex justify-between text-stone-600 dark:text-stone-300">
              <span>Approve / Decline confirmation</span>
              <kbd className="font-mono text-[11px]">Y / N</kbd>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
