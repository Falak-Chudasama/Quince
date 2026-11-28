import { BridgeError } from '../../shared/errors.js';
import { contentState } from '../state.js';

interface ParsedKey {
  key: string;
  code: string;
  keyCode: number;
  ctrlKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
  metaKey: boolean;
}

const SPECIAL_KEYS: Record<string, { key: string; code: string; keyCode: number }> = {
  enter: { key: 'Enter', code: 'Enter', keyCode: 13 },
  escape: { key: 'Escape', code: 'Escape', keyCode: 27 },
  esc: { key: 'Escape', code: 'Escape', keyCode: 27 },
  tab: { key: 'Tab', code: 'Tab', keyCode: 9 },
  backspace: { key: 'Backspace', code: 'Backspace', keyCode: 8 },
  delete: { key: 'Delete', code: 'Delete', keyCode: 46 },
  space: { key: ' ', code: 'Space', keyCode: 32 },
  arrowup: { key: 'ArrowUp', code: 'ArrowUp', keyCode: 38 },
  arrowdown: { key: 'ArrowDown', code: 'ArrowDown', keyCode: 40 },
  arrowleft: { key: 'ArrowLeft', code: 'ArrowLeft', keyCode: 37 },
  arrowright: { key: 'ArrowRight', code: 'ArrowRight', keyCode: 39 },
  pageup: { key: 'PageUp', code: 'PageUp', keyCode: 33 },
  pagedown: { key: 'PageDown', code: 'PageDown', keyCode: 34 },
  home: { key: 'Home', code: 'Home', keyCode: 36 },
  end: { key: 'End', code: 'End', keyCode: 35 },
};

export function parseKeyCombo(combo: string): ParsedKey {
  const parts = combo.split('+').map((p) => p.trim()).filter(Boolean);
  let ctrlKey = false;
  let shiftKey = false;
  let altKey = false;
  let metaKey = false;

  const baseRaw = parts.pop() || 'Enter';
  for (const mod of parts) {
    const m = mod.toLowerCase();
    if (m === 'control' || m === 'ctrl') ctrlKey = true;
    else if (m === 'shift') shiftKey = true;
    else if (m === 'alt') altKey = true;
    else if (m === 'meta' || m === 'cmd' || m === 'command') metaKey = true;
  }

  const special = SPECIAL_KEYS[baseRaw.toLowerCase()];
  if (special) {
    return { ...special, ctrlKey, shiftKey, altKey, metaKey };
  }

  if (baseRaw.length === 1) {
    const upper = baseRaw.toUpperCase();
    const isLetter = upper >= 'A' && upper <= 'Z';
    const isDigit = upper >= '0' && upper <= '9';
    return {
      key: shiftKey ? upper : baseRaw.toLowerCase(),
      code: isLetter ? `Key${upper}` : isDigit ? `Digit${upper}` : baseRaw,
      keyCode: upper.charCodeAt(0),
      ctrlKey,
      shiftKey,
      altKey,
      metaKey,
    };
  }

  return {
    key: baseRaw,
    code: baseRaw,
    keyCode: 0,
    ctrlKey,
    shiftKey,
    altKey,
    metaKey,
  };
}

export function dispatchKeySequence(target: Element, parsed: ParsedKey): boolean {
  const keyInit: KeyboardEventInit = {
    key: parsed.key,
    code: parsed.code,
    keyCode: parsed.keyCode,
    which: parsed.keyCode,
    ctrlKey: parsed.ctrlKey,
    shiftKey: parsed.shiftKey,
    altKey: parsed.altKey,
    metaKey: parsed.metaKey,
    bubbles: true,
    cancelable: true,
  };

  const downNotCancelled = target.dispatchEvent(new KeyboardEvent('keydown', keyInit));
  if (parsed.key === 'Enter' || parsed.key.length === 1) {
    target.dispatchEvent(new KeyboardEvent('keypress', { ...keyInit, charCode: parsed.keyCode }));
  }
  target.dispatchEvent(new KeyboardEvent('keyup', keyInit));
  return downNotCancelled;
}

export async function dispatchEnterWithFormFallback(el: Element, waitMs: number = 400): Promise<void> {
  const urlBefore = window.location.href;
  let significantMutation = false;

  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if ((m.target as Element)?.closest?.('[data-quince-overlay]')) {
        continue;
      }
      if (m.type === 'childList' && (m.addedNodes.length > 0 || m.removedNodes.length > 0)) {
        significantMutation = true;
        break;
      }
      if (m.type === 'attributes' && ['aria-expanded', 'hidden', 'open', 'class', 'style'].includes(m.attributeName || '')) {
        significantMutation = true;
        break;
      }
    }
  });

  observer.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
  });

  const parsedEnter = parseKeyCombo('Enter');
  dispatchKeySequence(el, parsedEnter);

  const start = Date.now();
  while (Date.now() - start < waitMs) {
    if (window.location.href !== urlBefore || significantMutation) {
      break;
    }
    await new Promise((r) => setTimeout(r, 50));
  }

  observer.disconnect();

  if (window.location.href === urlBefore && !significantMutation) {
    const form = el.closest('form');
    if (form) {
      const submitBtn = form.querySelector<HTMLElement>(
        'button[type="submit"]:not([disabled]), input[type="submit"]:not([disabled]), button:not([type]):not([disabled])'
      );
      if (typeof form.requestSubmit === 'function') {
        try {
          if (submitBtn) {
            form.requestSubmit(submitBtn);
          } else {
            form.requestSubmit();
          }
        } catch {
          submitBtn?.click();
        }
      } else if (submitBtn) {
        submitBtn.click();
      } else {
        form.submit();
      }
    }
  }
}

export async function executePressKey(key: string, ref?: string): Promise<void> {
  let target: Element = document.activeElement || document.body || document.documentElement;
  if (ref) {
    const el = contentState.getElement(ref);
    if (!el) {
      throw new BridgeError('not_found', `Element with ref ${ref} not found on page`);
    }
    target = el;
    if (el instanceof HTMLElement) {
      el.focus();
    }
  }

  const parsed = parseKeyCombo(key);

  if (parsed.key === 'Enter') {
    contentState.unsubmittedEdit = null;
    await dispatchEnterWithFormFallback(target, 400);
    return;
  }

  const downNotCancelled = dispatchKeySequence(target, parsed);

  // Synthetic Control+a / Meta+a does not select text natively in Chrome
  if (downNotCancelled && (parsed.ctrlKey || parsed.metaKey) && parsed.key.toLowerCase() === 'a') {
    if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
      target.select();
    } else if ((target as HTMLElement).isContentEditable) {
      const range = document.createRange();
      range.selectNodeContents(target);
      const sel = window.getSelection();
      sel?.removeAllRanges();
      sel?.addRange(range);
    }
  }
}
