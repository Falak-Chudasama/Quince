import { getAccessibleName } from './accname.js';
import { INTERACTIVE_ROLES, getElementRole } from './roles.js';
import { Capture, ElementSnapshotItem, contentState } from './state.js';
import { isElementVisible, isInViewport } from './visibility.js';

export type CausalOutcome = 'NAVIGATED' | 'DOM_UPDATED' | 'VALUE_CHANGED' | 'SCROLLED' | 'NO_EFFECT';

export function captureState(): Capture {
  const els = new Map<string, ElementSnapshotItem>();
  const messages: string[] = [];
  let modalRef: string | undefined;

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

    if (INTERACTIVE_ROLES.has(role)) {
      const ref = contentState.getOrCreateRef(el);
      const name = getAccessibleName(el);
      const inVp = isInViewport(el);

      if (role === 'dialog' || el.getAttribute('aria-modal') === 'true') {
        modalRef = ref;
      }

      const item: ElementSnapshotItem = {
        role,
        name,
        inViewport: inVp,
      };

      if (el instanceof HTMLInputElement) {
        item.value = el.type === 'password' ? '[REDACTED]' : el.value;
        if (el.type === 'checkbox' || el.type === 'radio') {
          item.checked = el.checked;
        }
      } else if (el instanceof HTMLTextAreaElement) {
        item.value = el.value;
      } else if (el instanceof HTMLSelectElement) {
        item.value = el.value;
      }
      if (el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true') {
        item.disabled = true;
      }
      const exp = el.getAttribute('aria-expanded');
      if (exp === 'true' || exp === 'false') {
        item.expanded = exp;
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

  let activeEl: Element | null = document.activeElement;
  while (activeEl && activeEl.shadowRoot && activeEl.shadowRoot.activeElement) {
    activeEl = activeEl.shadowRoot.activeElement;
  }
  const focusRef = activeEl ? contentState.elToRef.get(activeEl) : undefined;
  const focusRole = activeEl && activeEl !== document.body ? getElementRole(activeEl) : undefined;
  let focusValue: string | undefined;
  if (activeEl instanceof HTMLInputElement || activeEl instanceof HTMLTextAreaElement) {
    focusValue = activeEl.type === 'password' ? '[REDACTED]' : activeEl.value.slice(0, 40);
  }

  const vh = window.innerHeight || document.documentElement.clientHeight || 800;
  const scroll = window.scrollY || document.documentElement.scrollTop || 0;
  const scrollHeight = Math.max(
    document.documentElement.scrollHeight || 0,
    document.body?.scrollHeight || 0,
    vh
  );
  const maxScroll = Math.max(0, scrollHeight - vh);

  return {
    url: window.location.href,
    title: document.title || '',
    scroll,
    maxScroll,
    viewportHeight: vh,
    focusRef,
    focusRole,
    focusValue,
    els,
    messages,
    modalRef,
  };
}

export function computeStateChange(
  pre: Capture,
  post: Capture,
  waitInfo: { settled: boolean; reason: string; elapsed_ms: number; mutation_count?: number },
  actionMeta?: { method?: string; ref?: string; targetRole?: string; containerScrolled?: boolean }
): any {
  const added: Array<{ ref: string; desc: string; role: string; in_viewport?: boolean }> = [];
  const removed: Array<{ ref: string; desc: string; role: string }> = [];
  const changed: Array<{ ref: string; desc: string; fields: Record<string, [any, any]> }> = [];

  for (const [ref, afterItem] of post.els.entries()) {
    const beforeItem = pre.els.get(ref);
    if (!beforeItem) {
      added.push({
        ref,
        role: afterItem.role,
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
      if (beforeItem.expanded !== afterItem.expanded) {
        fields.expanded = [String(beforeItem.expanded), String(afterItem.expanded)];
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
        role: beforeItem.role,
        desc: `${beforeItem.role} "${beforeItem.name}"`,
      });
    }
  }

  const navigated = pre.url !== post.url;
  const scrollMoved = Math.abs(post.scroll - pre.scroll) > 2 || Boolean(actionMeta?.containerScrolled);
  const autocompleteAppeared = added.some((a) => a.role === 'listbox' || a.role === 'option');
  const modalOpened =
    Boolean(post.modalRef && post.modalRef !== pre.modalRef) ||
    added.some((a) => a.role === 'dialog');
  const structuralChange =
    added.length > 0 ||
    removed.length > 0 ||
    changed.some((c) => c.fields.expanded !== undefined || c.fields.disabled !== undefined) ||
    modalOpened;
  const valueChanged = changed.some(
    (c) => c.fields.value !== undefined || c.fields.checked !== undefined
  );

  let causalOutcome: CausalOutcome = 'NO_EFFECT';
  let effect: 'none' | 'dom_changed' | 'navigated' | 'value_set' = 'none';

  if (navigated) {
    causalOutcome = 'NAVIGATED';
    effect = 'navigated';
  } else if (structuralChange) {
    causalOutcome = 'DOM_UPDATED';
    effect = 'dom_changed';
  } else if (valueChanged) {
    causalOutcome = 'VALUE_CHANGED';
    effect = 'value_set';
  } else if (scrollMoved) {
    causalOutcome = 'SCROLLED';
    effect = 'none';
  }

  const noVisibleChange = causalOutcome === 'NO_EFFECT' && post.messages.length === 0;

  // Build summary line
  let summary = `OUTCOME: ${causalOutcome}`;
  if (navigated) {
    summary += ` | Navigated to ${post.title || post.url}`;
  } else if (causalOutcome === 'DOM_UPDATED') {
    summary += ` | +${added.length} -${removed.length} elements`;
  } else if (causalOutcome === 'VALUE_CHANGED') {
    summary += ' | Value updated';
  } else if (causalOutcome === 'SCROLLED') {
    const pct = post.maxScroll > 0 ? Math.round((post.scroll / post.maxScroll) * 100) : 0;
    summary += ` | Scrolled to ${pct}%`;
  } else {
    summary += ' | No visible change';
  }

  const newMessages = post.messages.filter((m) => !pre.messages.includes(m)).slice(0, 3);

  const revealedHeadings: string[] = [];
  if (causalOutcome === 'SCROLLED') {
    for (const [ref, item] of post.els.entries()) {
      const prev = pre.els.get(ref);
      if (item.role === 'heading' && item.inViewport && (!prev || !prev.inViewport)) {
        revealedHeadings.push(`[${ref}] "${item.name}"`);
        if (revealedHeadings.length >= 3) break;
      }
    }
  }

  const scrollPct = post.maxScroll > 0 ? Math.round((post.scroll / post.maxScroll) * 100) : 0;
  const atBottom = post.maxScroll <= 2 || post.scroll >= post.maxScroll - 2;
  const targetRef = actionMeta?.ref;
  const targetRole =
    actionMeta?.targetRole ||
    (targetRef ? post.els.get(targetRef)?.role || pre.els.get(targetRef)?.role : undefined);
  const stateFingerprint = `${post.url}|${Math.round(post.scroll)}|${post.focusRef || ''}|${post.modalRef || ''}|${post.els.size}`;

  return {
    effect,
    causal_outcome: causalOutcome,
    summary_line: summary.slice(0, 220),
    before: { url: pre.url, title: pre.title, scroll: pre.scroll },
    after: {
      url: post.url,
      title: post.title,
      scroll: post.scroll,
      generation: contentState.generation,
      state_fingerprint: stateFingerprint,
    },
    navigated,
    target: targetRef ? { ref: targetRef, role: targetRole } : undefined,
    focus: {
      before: pre.focusRef,
      after: post.focusRef,
      after_desc: post.focusRef
        ? `${post.els.get(post.focusRef)?.role || post.focusRole || ''} "${post.els.get(post.focusRef)?.name || ''}"`.trim()
        : undefined,
      after_role: post.focusRole,
      after_value: post.focusValue,
    },
    autocomplete_appeared: autocompleteAppeared,
    modal_opened: modalOpened,
    modal_ref: post.modalRef,
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
      pct: scrollPct,
      at_bottom: atBottom,
      revealed_headings: revealedHeadings,
    },
    state_fingerprint: stateFingerprint,
    wait: {
      settled: waitInfo.settled,
      reason: waitInfo.reason,
      elapsed_ms: waitInfo.elapsed_ms,
      mutation_count: waitInfo.mutation_count || 0,
    },
  };
}
