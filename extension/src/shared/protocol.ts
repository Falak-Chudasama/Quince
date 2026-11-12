import { PROTOCOL_VERSION } from './constants.js';
import { BridgeMessage } from './types.js';

export function makeHello(token: string, version: string = '0.1.0'): any {
  return {
    v: PROTOCOL_VERSION,
    type: 'hello',
    client: 'quince-extension',
    version,
    token,
    browser: 'Chrome',
    capabilities: ['snapshot', 'actions', 'risk_gate', 'diff', 'tabs', 'wait'],
  };
}

export function makeResponse(id: string, result: Record<string, any>): any {
  return {
    v: PROTOCOL_VERSION,
    type: 'response',
    id,
    ok: true,
    result,
  };
}

export function makeErrorResponse(
  id: string,
  code: string,
  message: string,
  options?: { retryable?: boolean; data?: Record<string, any> }
): any {
  return {
    v: PROTOCOL_VERSION,
    type: 'response',
    id,
    ok: false,
    error: {
      code,
      message,
      retryable: options?.retryable ?? false,
      data: options?.data ?? {},
    },
  };
}

export function makeEvent(event: string, params: Record<string, any>): any {
  return {
    v: PROTOCOL_VERSION,
    type: 'event',
    event,
    params,
  };
}

export function makePong(t?: number): any {
  return {
    v: PROTOCOL_VERSION,
    type: 'pong',
    t: t || Date.now(),
  };
}
