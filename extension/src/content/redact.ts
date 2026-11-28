export function isSensitiveField(el: Element): boolean {
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
    if (el instanceof HTMLInputElement) {
      if (el.type === 'password') return true;
      const ac = (el.autocomplete || '').toLowerCase();
      if (ac.includes('password') || ac.includes('cc-') || ac.includes('one-time-code')) {
        return true;
      }
    }
    const hints = [
      el.getAttribute('name') || '',
      el.id || '',
      el.getAttribute('placeholder') || '',
      el.getAttribute('aria-label') || '',
    ]
      .join(' ')
      .toLowerCase();
    if (
      /(?:^|[^a-z0-9])(password|passcode|pin|cvc|cvv|ssn|otp|secret|token|card.?number|credit.?card)(?:$|[^a-z0-9])/.test(
        hints
      )
    ) {
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
