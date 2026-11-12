export class BridgeError extends Error {
  public readonly code: string;
  public readonly retryable: boolean;
  public readonly data: Record<string, any>;

  constructor(code: string, message: string = '', options?: { retryable?: boolean; data?: Record<string, any> }) {
    super(message || code);
    this.name = 'BridgeError';
    this.code = code;
    this.retryable = options?.retryable ?? false;
    this.data = options?.data ?? {};
  }

  toObject() {
    return {
      code: this.code,
      message: this.message,
      retryable: this.retryable,
      data: this.data,
    };
  }
}

export const RETRYABLE_CODES = new Set([
  'extension_not_connected',
  'bridge_timeout',
  'bridge_disconnected',
  'stale_ref',
  'offscreen',
]);
