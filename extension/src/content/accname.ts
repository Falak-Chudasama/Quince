export function getAccessibleName(el: Element): string {
  // 1. aria-labelledby
  const labelledBy = el.getAttribute('aria-labelledby');
  if (labelledBy) {
    const parts = labelledBy
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent?.trim() || '')
      .filter(Boolean);
    if (parts.length > 0) {
      return sanitizeName(parts.join(' '));
    }
  }

  // 2. aria-label
  const ariaLabel = el.getAttribute('aria-label');
  if (ariaLabel && ariaLabel.trim()) {
    return sanitizeName(ariaLabel);
  }

  // 3. Native labels for form elements
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement) {
    if (el.id) {
      const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (label && label.textContent?.trim()) {
        return sanitizeName(label.textContent);
      }
    }
    const parentLabel = el.closest('label');
    if (parentLabel && parentLabel.textContent?.trim()) {
      return sanitizeName(parentLabel.textContent);
    }
    if (el instanceof HTMLInputElement && (el.type === 'submit' || el.type === 'button') && el.value) {
      return sanitizeName(el.value);
    }
    if ((el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) && el.placeholder) {
      return sanitizeName(el.placeholder);
    }
  }

  // 4. Alt text on images
  if (el instanceof HTMLImageElement && el.alt) {
    return sanitizeName(el.alt);
  }

  // 5. Title attribute
  const title = el.getAttribute('title');
  if (title && title.trim()) {
    return sanitizeName(title);
  }

  // 6. Direct text content for interactive buttons, links, headings
  const tag = el.tagName.toLowerCase();
  if (tag === 'button' || tag === 'a' || /^h[1-6]$/.test(tag)) {
    const text = el.textContent || '';
    if (text.trim()) {
      return sanitizeName(text);
    }
  }

  return '';
}

function sanitizeName(name: string): string {
  // Strip control characters, normalize whitespace, truncate to 60 chars
  const clean = name
    .replace(/[\x00-\x1f\x7f]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return clean.slice(0, 60);
}
