import { BridgeError } from '../../shared/errors.js';
import { contentState } from '../state.js';

export interface ScrollParams {
  direction?: 'up' | 'down' | 'top' | 'bottom' | 'to_element';
  pages?: number;
  container_ref?: string;
  ref?: string;
  delta?: number;
  delta_y?: number;
  pixels?: number;
}

export function executeScroll(
  directionOrParams: ScrollParams | 'up' | 'down' | 'top' | 'bottom' | 'to_element' = 'down',
  refArg?: string
): void {
  const params: ScrollParams =
    typeof directionOrParams === 'string'
      ? { direction: directionOrParams, ref: refArg }
      : (directionOrParams || {});

  const direction = params.direction || 'down';

  if (direction === 'to_element') {
    const targetRef = params.ref || params.container_ref;
    if (!targetRef) {
      throw new BridgeError('invalid_argument', 'ref is required for scroll direction=to_element');
    }
    const el = contentState.getElement(targetRef);
    if (!el) {
      throw new BridgeError('not_found', `Element with ref ${targetRef} not found on page`);
    }
    el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
    return;
  }

  let target: Element | Window = window;
  const containerRef = params.container_ref || params.ref;
  if (containerRef) {
    const el = contentState.getElement(containerRef);
    if (!el) {
      throw new BridgeError('not_found', `Container with ref ${containerRef} not found on page`);
    }
    target = el;
  }

  const rawPixelDelta = params.delta ?? params.delta_y ?? params.pixels;
  const pages = typeof params.pages === 'number' && params.pages > 0 ? params.pages : 0.8;
  const baseHeight =
    target === window
      ? (window.innerHeight || document.documentElement.clientHeight || 800)
      : ((target as Element).clientHeight || window.innerHeight || 600);
  const delta =
    typeof rawPixelDelta === 'number' && Number.isFinite(rawPixelDelta)
      ? Math.abs(rawPixelDelta)
      : Math.round(baseHeight * pages);

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
