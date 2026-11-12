import { getAccessibleName } from './accname.js';
import { getElementRole } from './roles.js';
import { contentState } from './state.js';
import { isElementVisible, isInViewport } from './visibility.js';

export interface ElementSnapshotItem {
  role: string;
  name: string;
  value?: string;
  checked?: boolean;
  disabled?: boolean;
  inViewport?: boolean;
}

export interface Capture {
  url: string;
  title: string;
  scroll: number;
  maxScroll: number;
  focusRef?: string;
  els: Map<string, ElementSnapshotItem>;
  messages: string[];
}

export function captureState(): Capture {
  const els = new Map<string, ElementSnapshotItem>();
  const messages: string[] = [];

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
    const isInteractive = ['button', 'link', 'textbox', 'combobox', 'checkbox', 'radio', 'heading', 'dialog', 'alert'].includes(role);

    if (isInteractive) {
      const ref = contentState.getOrCreateRef(el);
      const name = getAccessibleName(el);
      const inVp = isInViewport(el);

      const item: ElementSnapshotItem = {
        role,
        name,
        inViewport: inVp,
      };

      if (el instanceof HTMLInputElement) {
        item.value = el.value;
        if (el.type === 'checkbox' || el.type === 'radio') {
          item.checked = el.checked;
        }
      }
      if (el.hasAttribute('disabled')) {
        item.disabled = true;
      }

      els.set(ref, item);
    }

    // Check toasts / alert live messages
    const live = el.getAttribute('aria-live') || el.getAttribute('role');
    if (live === 'assertive' || live === 'alert' || live === 'status' || el.classList.contains('toast')) {
      const txt = (el.textContent || '').trim();
      if (txt && !messages.includes(txt)) {
        messages.push(txt.slice(0, 140));
      }
    }

    el = walker.nextNode() as Element | null;
  }

  const activeEl = document.activeElement;
  const focusRef = activeEl ? contentState.elToRef.get(activeEl) : undefined;

  const scroll = window.scrollY || document.documentElement.scrollTop || 0;
  const maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);

  return {
    url: window.location.href,
    title: document.title || '',
    scroll,
    maxScroll,
    focusRef,
    els,
    messages,
  };
}

export function computeStateChange(
  pre: Capture,
  post: Capture,
  waitInfo: { settled: boolean; reason: string; elapsed_ms: number; mutation_count?: number }
): any {
  const added: Array<{ ref: string; desc: string; in_viewport?: boolean }> = [];
  const removed: Array<{ ref: string; desc: string }> = [];
  const changed: Array<{ ref: string; desc: string; fields: Record<string, [any, any]> }> = [];

  for (const [ref, afterItem] of post.els.entries()) {
    const beforeItem = pre.els.get(ref);
    if (!beforeItem) {
      added.push({
        ref,
        desc: `${afterItem.role} "${afterItem.name}"`,
        in_viewport: afterItem.inViewport,
      });
    } else {
      const fields: Record<string, [any, any]> = {};
      if (beforeItem.value !== afterItem.value) {
        fields.value = [beforeItem.value || '', afterItem.value || ''];
      }
      if (beforeItem.checked !== afterItem.checked) {
        fields.checked = [String(beforeItem.checked), String(afterItem.checked)];
      }
      if (beforeItem.disabled !== afterItem.disabled) {
        fields.disabled = [String(beforeItem.disabled), String(afterItem.disabled)];
      }

      if (Object.keys(fields).length > 0) {
        changed.push({
          ref,
          desc: `${afterItem.role} "${afterItem.name}"`,
          fields,
        });
      }
    }
  }

  for (const [ref, beforeItem] of pre.els.entries()) {
    if (!post.els.has(ref)) {
      removed.push({
        ref,
        desc: `${beforeItem.role} "${beforeItem.name}"`,
      });
    }
  }

  const navigated = pre.url !== post.url;
  let effect: 'none' | 'dom_changed' | 'navigated' | 'value_set' = 'none';

  if (navigated) {
    effect = 'navigated';
  } else if (changed.some((c) => c.fields.value !== undefined)) {
    effect = 'value_set';
  } else if (added.length > 0 || removed.length > 0 || changed.length > 0) {
    effect = 'dom_changed';
  }

  const noVisibleChange = effect === 'none' && !navigated && post.messages.length === 0;

  // Build summary line
  let summary = `EFFECT: ${effect}`;
  if (navigated) {
    summary += ` | Navigated to ${post.title || post.url}`;
  } else if (added.length > 0 || removed.length > 0) {
    summary += ` | +${added.length} -${removed.length} elements`;
  } else if (noVisibleChange) {
    summary += ' | No visible change';
  }

  const newMessages = post.messages.filter((m) => !pre.messages.includes(m)).slice(0, 3);

  return {
    effect,
    summary_line: summary.slice(0, 220),
    before: { url: pre.url, title: pre.title, scroll: pre.scroll },
    after: { url: post.url, title: post.title, scroll: post.scroll, generation: contentState.generation },
    navigated,
    dom: {
      added: added.slice(0, 25),
      removed: removed.slice(0, 25),
      changed: changed.slice(0, 25),
      overflow: {
        added: Math.max(0, added.length - 25),
        removed: Math.max(0, removed.length - 25),
        changed: Math.max(0, changed.length - 25),
      },
    },
    messages: newMessages,
    no_visible_change: noVisibleChange,
    scroll: {
      before: pre.scroll,
      after: post.scroll,
      max: post.maxScroll,
    },
    wait: {
      settled: waitInfo.settled,
      reason: waitInfo.reason,
      elapsed_ms: waitInfo.elapsed_ms,
      mutation_count: waitInfo.mutation_count || 0,
    },
  };
}
