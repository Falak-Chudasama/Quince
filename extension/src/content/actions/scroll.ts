import { BridgeError } from '../../shared/errors.js';
import { contentState } from '../state.js';

export function executeScroll(direction: 'up' | 'down' | 'top' | 'bottom' = 'down', ref?: string): void {
  let target: Element | Window = window;
  if (ref) {
    const el = contentState.getElement(ref);
    if (!el) {
      throw new BridgeError('not_found', `Element with ref ${ref} not found on page`);
    }
    target = el;
  }

  const delta = window.innerHeight * 0.75;

  if (target === window) {
    if (direction === 'top') {
      window.scrollTo({ top: 0, behavior: 'instant' });
    } else if (direction === 'bottom') {
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' });
    } else if (direction === 'up') {
      window.scrollBy({ top: -delta, behavior: 'instant' });
    } else {
      window.scrollBy({ top: delta, behavior: 'instant' });
    }
  } else {
    const el = target as Element;
    if (direction === 'top') {
      el.scrollTop = 0;
    } else if (direction === 'bottom') {
      el.scrollTop = el.scrollHeight;
    } else if (direction === 'up') {
      el.scrollTop -= delta;
    } else {
      el.scrollTop += delta;
    }
  }
}
