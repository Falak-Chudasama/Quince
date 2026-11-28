import { getAccessibleName } from './accname.js';
import { getElementRole } from './roles.js';
import { contentState } from './state.js';
import { getViewportPosition, isElementVisible } from './visibility.js';

interface FindResult {
  ref: string;
  role: string;
  name: string;
  position: 'in_viewport' | 'above' | 'below';
  score: number;
}

export function findInPage(
  query: string,
  maxResults: number = 5
): {
  results: Array<{ ref: string; role: string; name: string; position: 'in_viewport' | 'above' | 'below' }>;
  counts: { total: number; in_viewport: number; above_viewport: number; below_viewport: number };
} {
  const q = query.trim().toLowerCase();
  if (!q) {
    return {
      results: [],
      counts: { total: 0, in_viewport: 0, above_viewport: 0, below_viewport: 0 },
    };
  }

  const matches: FindResult[] = [];
  let inViewportCount = 0;
  let aboveCount = 0;
  let belowCount = 0;

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
      const position = getViewportPosition(el);
      if (position === 'in_viewport') inViewportCount++;
      else if (position === 'above') aboveCount++;
      else belowCount++;

      matches.push({ ref, role, name: name || text.slice(0, 40), position, score });
    }

    el = walker.nextNode() as Element | null;
  }

  matches.sort((a, b) => b.score - a.score);
  return {
    results: matches.slice(0, maxResults).map(({ ref, role, name, position }) => ({ ref, role, name, position })),
    counts: {
      total: matches.length,
      in_viewport: inViewportCount,
      above_viewport: aboveCount,
      below_viewport: belowCount,
    },
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
