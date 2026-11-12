import { getAccessibleName } from './accname.js';
import { getElementRole } from './roles.js';
import { contentState } from './state.js';
import { isElementVisible } from './visibility.js';

interface FindResult {
  ref: string;
  role: string;
  name: string;
  score: number;
}

export function findInPage(query: string, maxResults: number = 5): { results: Array<{ ref: string; role: string; name: string }> } {
  const q = query.trim().toLowerCase();
  if (!q) return { results: [] };

  const matches: FindResult[] = [];

  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_ELEMENT, {
    acceptNode(node) {
      const el = node as Element;
      if (el.hasAttribute('data-quince-overlay') || !isElementVisible(el)) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });

  let el = walker.nextNode() as Element | null;
  while (el) {
    const role = getElementRole(el);
    const name = getAccessibleName(el);
    const text = (el.textContent || '').trim().toLowerCase();
    const nameLower = name.toLowerCase();

    let score = 0;
    if (nameLower === q) {
      score = 100;
    } else if (nameLower.startsWith(q)) {
      score = 80;
    } else if (nameLower.includes(q)) {
      score = 60;
    } else if (text.includes(q)) {
      score = 30;
    }

    if (score > 0) {
      const ref = contentState.getOrCreateRef(el);
      matches.push({ ref, role, name: name || text.slice(0, 40), score });
    }

    el = walker.nextNode() as Element | null;
  }

  matches.sort((a, b) => b.score - a.score);
  return {
    results: matches.slice(0, maxResults).map(({ ref, role, name }) => ({ ref, role, name })),
  };
}

export function readText(ref?: string, maxChars: number = 4000): { text: string } {
  let targetNode: Element = document.body || document.documentElement;
  if (ref) {
    const el = contentState.getElement(ref);
    if (el) {
      targetNode = el;
    }
  }

  const raw = (targetNode.textContent || '').replace(/\s+/g, ' ').trim();
  return {
    text: raw.slice(0, maxChars),
  };
}
