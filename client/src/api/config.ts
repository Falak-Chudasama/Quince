export interface EndpointConfig {
  basketApiUrl: string
  basketWsUrl: string
  quinceApiUrl: string
}

export function resolveEndpointConfig(
  env: Record<string, unknown> = import.meta.env as Record<string, unknown>,
  loc: { protocol?: string; hostname?: string } | undefined =
    typeof window !== 'undefined' ? window.location : undefined,
): EndpointConfig {
  const envBasketApi =
    typeof env.VITE_BASKET_API_URL === 'string' ? env.VITE_BASKET_API_URL.trim() : ''
  const envBasketWs =
    typeof env.VITE_BASKET_WS_URL === 'string' ? env.VITE_BASKET_WS_URL.trim() : ''
  const envQuinceApi =
    typeof env.VITE_QUINCE_API_URL === 'string' ? env.VITE_QUINCE_API_URL.trim() : ''

  const isJamOrHttps =
    loc?.protocol === 'https:' || Boolean(loc?.hostname?.endsWith('.jam'))

  const defaultBasketApi = isJamOrHttps
    ? 'https://api.basket.jam'
    : 'http://127.0.0.1:10010'
  const defaultBasketWs = isJamOrHttps
    ? 'wss://api.basket.jam/ws'
    : 'ws://127.0.0.1:10010/ws'
  const defaultQuinceApi = isJamOrHttps
    ? 'https://api.quince.jam'
    : 'http://127.0.0.5:10000'

  return {
    basketApiUrl: (envBasketApi || defaultBasketApi).replace(/\/+$/, ''),
    basketWsUrl: envBasketWs || defaultBasketWs,
    quinceApiUrl: (envQuinceApi || defaultQuinceApi).replace(/\/+$/, ''),
  }
}

const resolved = resolveEndpointConfig()

export const BASKET_API_URL = resolved.basketApiUrl
export const BASKET_WS_URL = resolved.basketWsUrl
export const QUINCE_API_URL = resolved.quinceApiUrl

export const DEFAULT_SETTINGS = {
  model: '',
  voice: 'jane',
  retrieveChat: true,
  retrieveNotes: true,
  synthesizeSpeech: false,
  temperature: 0.3,
  maxTokens: 2048,
}
