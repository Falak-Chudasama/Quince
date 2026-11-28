export function isElementVisible(el: Element): boolean {
  if (el.hasAttribute('aria-hidden') && el.getAttribute('aria-hidden') === 'true') {
    return false;
  }
  if (el.hasAttribute('inert')) {
    return false;
  }
  if ((el as HTMLElement).hidden) {
    return false;
  }

  // checkVisibility if available in Chrome 116+
  if (typeof (el as any).checkVisibility === 'function') {
    if (!(el as any).checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) {
      return false;
    }
  } else {
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
      return false;
    }
  }

  const rect = el.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    return false;
  }

  return true;
}

export function isInViewport(el: Element): boolean {
  const rect = el.getBoundingClientRect();
  const vh = window.innerHeight || document.documentElement.clientHeight;
  const vw = window.innerWidth || document.documentElement.clientWidth;

  return (
    rect.top < vh &&
    rect.bottom > 0 &&
    rect.left < vw &&
    rect.right > 0
  );
}

export function getViewportPosition(el: Element): 'in_viewport' | 'above' | 'below' {
  if (isInViewport(el)) {
    return 'in_viewport';
  }
  const rect = el.getBoundingClientRect();
  if (rect.bottom <= 0) {
    return 'above';
  }
  return 'below';
}

export function ensureInViewport(el: Element): void {
  const rect = el.getBoundingClientRect();
  const vh = window.innerHeight || document.documentElement.clientHeight;
  const vw = window.innerWidth || document.documentElement.clientWidth;
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const centerVisible = cy >= 0 && cy < vh && cx >= 0 && cx < vw;
  if (!isInViewport(el) || !centerVisible) {
    el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
  }
}
