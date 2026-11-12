export function getElementRole(el: Element): string {
  const explicit = el.getAttribute('role');
  if (explicit && explicit.trim()) {
    return explicit.trim().toLowerCase().split(/\s+/)[0]!;
  }

  const tag = el.tagName.toLowerCase();

  if (tag === 'a' && el.hasAttribute('href')) return 'link';
  if (tag === 'button') return 'button';
  if (tag === 'textarea') return 'textbox';
  if (tag === 'select') return (el as HTMLSelectElement).multiple ? 'listbox' : 'combobox';

  if (tag === 'input') {
    const type = ((el as HTMLInputElement).type || 'text').toLowerCase();
    switch (type) {
      case 'button':
      case 'submit':
      case 'reset':
      case 'image':
        return 'button';
      case 'checkbox':
        return 'checkbox';
      case 'radio':
        return 'radio';
      case 'range':
        return 'slider';
      case 'number':
        return 'spinbutton';
      case 'search':
        return 'searchbox';
      default:
        return 'textbox';
    }
  }

  if (/^h[1-6]$/.test(tag)) return 'heading';
  if (tag === 'img') return 'img';
  if (tag === 'hr') return 'separator';
  if (tag === 'dialog') return 'dialog';
  if (tag === 'nav') return 'navigation';
  if (tag === 'main') return 'main';
  if (tag === 'article') return 'article';

  return 'generic';
}
