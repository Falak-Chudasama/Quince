import { BridgeError } from '../../shared/errors.js';
import { isSensitiveField } from '../redact.js';
import { contentState } from '../state.js';
import { isElementVisible } from '../visibility.js';

export function executeType(
  ref: string,
  text: string,
  clearFirst: boolean = true,
  pressEnter: boolean = false
): void {
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

  el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });

  if (el instanceof HTMLElement) {
    el.focus();
  }

  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
    const proto = el instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
    const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;

    const newVal = clearFirst ? text : el.value + text;

    if (nativeSetter) {
      nativeSetter.call(el, newVal);
    } else {
      el.value = newVal;
    }

    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  } else if ((el as HTMLElement).isContentEditable) {
    if (clearFirst) {
      el.textContent = text;
    } else {
      el.textContent += text;
    }
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }

  if (pressEnter) {
    const keyInit: KeyboardEventInit = {
      key: 'Enter',
      code: 'Enter',
      keyCode: 13,
      which: 13,
      bubbles: true,
      cancelable: true,
    };
    el.dispatchEvent(new KeyboardEvent('keydown', keyInit));
    el.dispatchEvent(new KeyboardEvent('keypress', keyInit));
    el.dispatchEvent(new KeyboardEvent('keyup', keyInit));
  }
}
