import { BridgeError } from '../../shared/errors.js';
import { isSensitiveField } from '../redact.js';
import { getElementRole } from '../roles.js';
import { contentState } from '../state.js';
import { ensureInViewport, isElementVisible } from '../visibility.js';
import { dispatchEnterWithFormFallback } from './key.js';

function setNativeInputValue(el: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const proto = el instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
  const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  if (nativeSetter) {
    nativeSetter.call(el, value);
  } else {
    el.value = value;
  }
}

export async function executeType(
  ref: string,
  text: string,
  clear: boolean = true,
  submit: boolean = false
): Promise<void> {
  const el = contentState.getElement(ref);
  if (!el) {
    throw new BridgeError('not_found', `Element with ref ${ref} not found on page`);
  }
  if (!isElementVisible(el)) {
    throw new BridgeError('not_visible', `Element with ref ${ref} is not visible`);
  }
  if (isSensitiveField(el)) {
    throw new BridgeError('sensitive_field', 'Refused to type into sensitive or password field');
  }

  ensureInViewport(el);

  if (el instanceof HTMLElement) {
    el.focus();
  }

  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
    if (clear && el.value.length > 0) {
      setNativeInputValue(el, '');
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }

    const newVal = clear ? text : el.value + text;
    setNativeInputValue(el, newVal);

    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  } else if ((el as HTMLElement).isContentEditable) {
    if (clear) {
      el.textContent = text;
    } else {
      el.textContent = (el.textContent || '') + text;
    }
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }

  const role = getElementRole(el);
  if (submit) {
    contentState.unsubmittedEdit = null;
    await dispatchEnterWithFormFallback(el, 400);
  } else if (role === 'searchbox' || role === 'textbox' || role === 'combobox') {
    contentState.unsubmittedEdit = { ref, url: window.location.href };
  }
}
