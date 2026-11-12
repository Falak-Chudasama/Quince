import { BridgeError } from '../../shared/errors.js';
import { contentState } from '../state.js';
import { isElementVisible } from '../visibility.js';

export function executeClick(ref: string, clickType: 'single' | 'double' | 'right' = 'single'): void {
  const el = contentState.getElement(ref);
  if (!el) {
    throw new BridgeError('not_found', `Element with ref ${ref} not found on page`);
  }
  if (!isElementVisible(el)) {
    throw new BridgeError('not_visible', `Element with ref ${ref} is not visible`);
  }

  // Scroll into view if needed
  el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });

  const rect = el.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;

  // Check if covered by another element
  const topEl = document.elementFromPoint(x, y);
  if (topEl && !el.contains(topEl) && !topEl.contains(el)) {
    const topRole = topEl.getAttribute('role') || topEl.tagName.toLowerCase();
    throw new BridgeError('covered_by', `Element is covered by <${topRole}>`, {
      data: { covered_by: topRole },
    });
  }

  const mouseInit: MouseEventInit = {
    bubbles: true,
    cancelable: true,
    view: window,
    clientX: x,
    clientY: y,
    button: clickType === 'right' ? 2 : 0,
  };

  el.dispatchEvent(new MouseEvent('pointerdown', mouseInit));
  el.dispatchEvent(new MouseEvent('mousedown', mouseInit));
  el.dispatchEvent(new MouseEvent('pointerup', mouseInit));
  el.dispatchEvent(new MouseEvent('mouseup', mouseInit));

  if (clickType === 'right') {
    el.dispatchEvent(new MouseEvent('contextmenu', mouseInit));
  } else if (clickType === 'double') {
    el.dispatchEvent(new MouseEvent('click', mouseInit));
    el.dispatchEvent(new MouseEvent('click', mouseInit));
    el.dispatchEvent(new MouseEvent('dblclick', mouseInit));
  } else {
    el.dispatchEvent(new MouseEvent('click', mouseInit));
  }

  if (el instanceof HTMLElement) {
    el.focus();
  }
}
