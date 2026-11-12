export function isSensitiveField(el: Element): boolean {
  if (el instanceof HTMLInputElement) {
    if (el.type === 'password') return true;
    const ac = (el.autocomplete || '').toLowerCase();
    if (ac.includes('password') || ac.includes('cc-') || ac.includes('one-time-code')) {
      return true;
    }
    const nameOrId = `${el.name || ''} ${el.id || ''}`.toLowerCase();
    if (/\b(password|passcode|pin|cvc|cvv|ssn|otp|secret)\b/.test(nameOrId)) {
      return true;
    }
  }
  return false;
}

export function sanitizeValue(el: Element, val: string): string {
  if (isSensitiveField(el)) {
    return '[REDACTED]';
  }
  return val;
}
