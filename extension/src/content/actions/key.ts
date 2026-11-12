import { BridgeError } from '../../shared/errors.js';
import { contentState } from '../state.js';

export function executePressKey(key: string, ref?: string): void {
  let target: Element = document.activeElement || document.body;
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

  const keyInit: KeyboardEventInit = {
    key,
    bubbles: true,
    cancelable: true,
  };

  target.dispatchEvent(new KeyboardEvent('keydown', keyInit));
  target.dispatchEvent(new KeyboardEvent('keypress', keyInit));
  target.dispatchEvent(new KeyboardEvent('keyup', keyInit));
}
