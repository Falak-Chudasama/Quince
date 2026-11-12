import { BridgeError } from '../../shared/errors.js';
import { contentState } from '../state.js';

export function executeHover(ref: string): void {
  const el = contentState.getElement(ref);
  if (!el) {
    throw new BridgeError('not_found', `Element with ref ${ref} not found`);
  }

  el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
  const rect = el.getBoundingClientRect();
  const mouseInit: MouseEventInit = {
    bubbles: true,
    cancelable: true,
    view: window,
    clientX: rect.left + rect.width / 2,
    clientY: rect.top + rect.height / 2,
  };

  el.dispatchEvent(new MouseEvent('pointerover', mouseInit));
  el.dispatchEvent(new MouseEvent('pointerenter', mouseInit));
  el.dispatchEvent(new MouseEvent('mouseover', mouseInit));
  el.dispatchEvent(new MouseEvent('mouseenter', mouseInit));
}

export function executeSetChecked(ref: string, checked: boolean): void {
  const el = contentState.getElement(ref);
  if (!el || !(el instanceof HTMLInputElement) || (el.type !== 'checkbox' && el.type !== 'radio')) {
    throw new BridgeError('not_found', `Checkbox or radio element with ref ${ref} not found`);
  }

  if (el.checked !== checked) {
    el.checked = checked;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
}
