import { getAccessibleName } from './accname.js';
import { sanitizeValue } from './redact.js';
import { getElementRole } from './roles.js';
import { contentState } from './state.js';
import { isElementVisible, isInViewport } from './visibility.js';

interface SnapshotItem {
  ref: string;
  line: string;
  inViewport: boolean;
  el: Element;
}

export function generateSnapshot(options?: { scope?: 'viewport' | 'full'; max_chars?: number }): {
  text: string;
  generation: number;
  page: { url: string; title: string };
  observation_meta: { url: string; title: string };
} {
  const maxChars = options?.max_chars || 6000;
  const scope = options?.scope || 'viewport';

  const items: SnapshotItem[] = [];

  function traverse(root: Element | DocumentFragment) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, {
      acceptNode(node) {
        const el = node as Element;
        if (el.hasAttribute('data-quince-overlay')) {
          return NodeFilter.FILTER_REJECT;
        }
        const tag = el.tagName.toLowerCase();
        if (['script', 'style', 'noscript', 'meta', 'link', 'svg'].includes(tag)) {
          return NodeFilter.FILTER_REJECT;
        }
        if (!isElementVisible(el)) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    });

    let current = walker.nextNode() as Element | null;
    while (current) {
      // Check shadow root
      if (current.shadowRoot) {
        traverse(current.shadowRoot);
      }

      const role = getElementRole(current);
      const isInteractive = [
        'button', 'link', 'textbox', 'combobox', 'checkbox', 'radio',
        'heading', 'searchbox', 'slider', 'spinbutton', 'dialog', 'alert'
      ].includes(role);

      if (isInteractive) {
        const ref = contentState.getOrCreateRef(current);
        const name = getAccessibleName(current);
        const inVp = isInViewport(current);

        let extraAttrs = '';
        if (current instanceof HTMLInputElement) {
          if (current.type && current.type !== 'text') {
            extraAttrs += ` type=${current.type}`;
          }
          if (current.type === 'checkbox' || current.type === 'radio') {
            extraAttrs += ` checked=${current.checked}`;
          }
          if (current.value && current.type !== 'password') {
            extraAttrs += ` value="${sanitizeValue(current, current.value.slice(0, 40))}"`;
          }
        }
        if (current.hasAttribute('disabled')) {
          extraAttrs += ' disabled=true';
        }

        const tag = current.tagName.toLowerCase();
        let displayRole = role;
        if (/^h([1-6])$/.test(tag)) {
          displayRole = `heading(${RegExp.$1})`;
        }

        const line = name
          ? `[${ref}] ${displayRole} "${name}"${extraAttrs}`
          : `[${ref}] ${displayRole}${extraAttrs}`;

        items.push({ ref, line, inViewport: inVp, el: current });
        contentState.descriptors.set(ref, {
          role,
          name,
          tag,
          inViewport: inVp,
        });
      }

      current = walker.nextNode() as Element | null;
    }
  }

  traverse(document.body || document.documentElement);

  // Filter or sort by viewport
  let selected = items;
  if (scope === 'viewport') {
    selected = items.filter((i) => i.inViewport);
    if (selected.length === 0) {
      selected = items.slice(0, 30); // fallback if viewport calc is off
    }
  } else {
    // Viewport first, then rest
    selected = [...items].sort((a, b) => (b.inViewport ? 1 : 0) - (a.inViewport ? 1 : 0));
  }

  // Format under maxChars budget
  const lines: string[] = [];
  let currentLen = 0;
  let truncatedCount = 0;

  for (const item of selected) {
    if (currentLen + item.line.length + 1 > maxChars - 100) {
      truncatedCount++;
    } else {
      lines.push(item.line);
      currentLen += item.line.length + 1;
    }
  }

  if (truncatedCount > 0) {
    lines.push(`... (+${truncatedCount} more elements omitted)`);
  }

  contentState.generation++;

  const page = {
    url: window.location.href,
    title: document.title || '',
  };

  return {
    text: lines.join('\n'),
    generation: contentState.generation,
    page,
    observation_meta: page,
  };
}
