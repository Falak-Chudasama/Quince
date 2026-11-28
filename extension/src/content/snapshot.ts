import { getAccessibleName } from './accname.js';
import { sanitizeValue } from './redact.js';
import { INTERACTIVE_ROLES, getElementRole } from './roles.js';
import { contentState } from './state.js';
import { getViewportPosition, isElementVisible, isInViewport } from './visibility.js';

interface SnapshotItem {
  ref: string;
  line: string;
  inViewport: boolean;
  inModal: boolean;
  el: Element;
}

function getDeepActiveElement(): Element | null {
  let active: Element | null = document.activeElement;
  while (active && active.shadowRoot && active.shadowRoot.activeElement) {
    active = active.shadowRoot.activeElement;
  }
  return active;
}

function isSearchLikeInput(el: Element, role: string, name: string): boolean {
  if (role === 'searchbox') return true;
  if (role !== 'textbox' && role !== 'combobox') return false;
  if (el.getAttribute('enterkeyhint')?.toLowerCase() === 'search') return true;
  if (el.closest('[role="search"]')) return true;
  const form = el.closest('form');
  if (form && form.querySelectorAll('input:not([type="hidden"])').length === 1) {
    return true;
  }
  const hints = `${name} ${el.getAttribute('name') || ''} ${el.getAttribute('id') || ''} ${el.getAttribute('placeholder') || ''}`;
  return /\b(search|query|find|lookup)\b/i.test(hints);
}

function findTopOpenModal(): Element | null {
  const candidates = Array.from(
    document.querySelectorAll('[role="dialog"], [aria-modal="true"], dialog[open]')
  ).filter((el) => !el.hasAttribute('data-quince-overlay') && isElementVisible(el));
  if (candidates.length === 0) return null;
  return candidates[candidates.length - 1] || null;
}

function truncStr(s: string, maxLen: number): string {
  return s.length <= maxLen ? s : s.slice(0, maxLen - 1) + '…';
}

export function generateSnapshot(options?: { scope?: 'viewport' | 'full'; max_chars?: number }): {
  text: string;
  generation: number;
  page: { url: string; title: string };
  observation_meta: Record<string, any>;
} {
  const maxChars = options?.max_chars || 6000;
  const scope = options?.scope || 'viewport';

  const url = window.location.href;
  const title = document.title || '';

  if (contentState.unsubmittedEdit && contentState.unsubmittedEdit.url !== url) {
    contentState.unsubmittedEdit = null;
  }

  const activeEl = getDeepActiveElement();
  const modalEl = findTopOpenModal();

  const items: SnapshotItem[] = [];
  const scrollableContainers: Array<{ ref: string; role: string; name: string }> = [];

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
      if (current.shadowRoot) {
        traverse(current.shadowRoot);
      }

      const role = getElementRole(current);
      const name = getAccessibleName(current);

      // Detect major inner scrollable containers
      if (
        scrollableContainers.length < 3 &&
        current !== document.body &&
        current !== document.documentElement &&
        current.clientHeight >= 100 &&
        current.scrollHeight > current.clientHeight + 40
      ) {
        const style = window.getComputedStyle(current);
        if (style.overflowY === 'auto' || style.overflowY === 'scroll' || style.overflowY === 'overlay') {
          const cRef = contentState.getOrCreateRef(current);
          scrollableContainers.push({ ref: cRef, role, name: truncStr(name, 30) });
        }
      }

      if (INTERACTIVE_ROLES.has(role)) {
        const ref = contentState.getOrCreateRef(current);
        const inVp = isInViewport(current);
        const inModal = modalEl ? modalEl.contains(current) : false;

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
        } else if (current instanceof HTMLTextAreaElement && current.value) {
          extraAttrs += ` value="${sanitizeValue(current, current.value.slice(0, 40))}"`;
        } else if (current instanceof HTMLSelectElement && current.selectedOptions.length > 0) {
          extraAttrs += ` value="${truncStr(current.selectedOptions[0]?.text || '', 30)}"`;
        }

        // Compact Element Affordance Tags
        const tags: string[] = [];
        if (current === activeEl) {
          tags.push('[focused]');
        }
        if (isSearchLikeInput(current, role, name)) {
          tags.push('[searchbox, enter-submits]');
        }
        const expanded = current.getAttribute('aria-expanded');
        if (expanded === 'true' || expanded === 'false') {
          tags.push(`[expanded=${expanded}]`);
        }
        const isChecked =
          (current instanceof HTMLInputElement && (current.type === 'checkbox' || current.type === 'radio') && current.checked) ||
          current.getAttribute('aria-checked') === 'true';
        if (isChecked) {
          tags.push('[checked]');
        }
        const isDisabled =
          current.hasAttribute('disabled') || current.getAttribute('aria-disabled') === 'true';
        if (isDisabled) {
          tags.push('[disabled]');
        }
        if (!inVp) {
          const pos = getViewportPosition(current);
          if (pos === 'above' || pos === 'below') {
            tags.push(`[offscreen: ${pos}]`);
          }
        }

        const tag = current.tagName.toLowerCase();
        let displayRole = role;
        if (/^h([1-6])$/.test(tag)) {
          displayRole = `heading(${RegExp.$1})`;
        }

        const tagStr = tags.length > 0 ? ' ' + tags.join(' ') : '';
        const line = name
          ? `[${ref}] ${displayRole} "${name}"${extraAttrs}${tagStr}`
          : `[${ref}] ${displayRole}${extraAttrs}${tagStr}`;

        items.push({ ref, line, inViewport: inVp, inModal, el: current });
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

  // Viewport geometry
  const vh = window.innerHeight || document.documentElement.clientHeight || 800;
  const scrollTop = window.scrollY || document.documentElement.scrollTop || 0;
  const scrollHeight = Math.max(
    document.documentElement.scrollHeight || 0,
    document.body?.scrollHeight || 0,
    vh
  );
  const maxScroll = Math.max(0, scrollHeight - vh);
  const scrollPct = maxScroll > 0 ? Math.round((scrollTop / maxScroll) * 100) : 0;
  const atTop = scrollTop <= 2;
  const atBottom = maxScroll <= 2 || scrollTop >= maxScroll - 2;
  const screensAbove = vh > 0 ? Math.round((scrollTop / vh) * 10) / 10 : 0;
  const screensBelow = vh > 0 ? Math.round((Math.max(0, maxScroll - scrollTop) / vh) * 10) / 10 : 0;

  const canScroll: string[] = [];
  if (maxScroll > 2) {
    if (!atTop) canScroll.push('up');
    if (!atBottom) canScroll.push('down');
  }

  // Focus metadata
  let focusMeta: Record<string, any> | null = null;
  if (
    activeEl &&
    activeEl !== document.body &&
    activeEl !== document.documentElement &&
    !activeEl.hasAttribute('data-quince-overlay') &&
    isElementVisible(activeEl)
  ) {
    const fRef = contentState.getOrCreateRef(activeEl);
    const fRole = getElementRole(activeEl);
    const fName = getAccessibleName(activeEl);
    let fValue = '';
    if (activeEl instanceof HTMLInputElement || activeEl instanceof HTMLTextAreaElement) {
      fValue = activeEl.type === 'password' ? '[REDACTED]' : sanitizeValue(activeEl, activeEl.value.slice(0, 40));
    } else if ((activeEl as HTMLElement).isContentEditable) {
      fValue = (activeEl.textContent || '').trim().slice(0, 40);
    }
    const unsubmitted =
      Boolean(fValue) &&
      (isSearchLikeInput(activeEl, fRole, fName) ||
        (contentState.unsubmittedEdit?.ref === fRef && contentState.unsubmittedEdit?.url === url));
    focusMeta = {
      ref: fRef,
      role: fRole,
      value: fValue,
      unsubmitted,
    };
  }

  // Modal metadata
  let modalMeta: Record<string, any> | null = null;
  if (modalEl) {
    const mRef = contentState.getOrCreateRef(modalEl);
    const mRole = getElementRole(modalEl);
    const mName = truncStr(getAccessibleName(modalEl), 40);
    const interactiveRefs = items.filter((i) => i.inModal).map((i) => i.ref);
    modalMeta = {
      ref: mRef,
      role: mRole,
      name: mName,
      interactive_refs: interactiveRefs.slice(0, 20),
    };
  }

  // Select and hoist modal items
  let selected = items;
  if (scope === 'viewport') {
    selected = items.filter((i) => i.inViewport || i.inModal || i.el === activeEl);
    if (selected.length === 0) {
      selected = items.slice(0, 30);
    }
  } else {
    selected = [...items].sort((a, b) => (b.inViewport ? 1 : 0) - (a.inViewport ? 1 : 0));
  }

  if (modalEl) {
    const modalItems = selected.filter((i) => i.inModal);
    const otherItems = selected.filter((i) => !i.inModal);
    selected = [...modalItems, ...otherItems];
  }

  // Build deterministic Page State Header (~50-70 tokens)
  const headerLines: string[] = [];
  headerLines.push(`[PAGE] ${truncStr(title || '(untitled)', 50)} | ${truncStr(url, 80)}`);

  const flags: string[] = [];
  if (atTop) flags.push('AT TOP');
  if (atBottom) flags.push('AT BOTTOM');
  const flagStr = flags.length > 0 ? ' ' + flags.join(' ') : '';
  const canScrollStr = canScroll.length > 0 ? canScroll.join(',') : 'none';
  const containerStr =
    scrollableContainers.length > 0
      ? ` | containers: ${scrollableContainers.map((c) => `[${c.ref}]`).join(',')}`
      : '';
  headerLines.push(
    `[VIEWPORT] ${scrollPct}%${flagStr} | ~${screensAbove.toFixed(1)} above | ~${screensBelow.toFixed(1)} below | can_scroll: ${canScrollStr}${containerStr}`
  );

  if (focusMeta) {
    const valPart = focusMeta.value ? ` value="${truncStr(focusMeta.value, 30)}"` : '';
    const unsubPart = focusMeta.unsubmitted
      ? ' (UNSUBMITTED — press Enter or click submit button)'
      : '';
    headerLines.push(`[FOCUS] [${focusMeta.ref}] ${focusMeta.role}${valPart}${unsubPart}`);
  } else {
    headerLines.push('[FOCUS] none');
  }

  if (modalMeta) {
    const mNamePart = modalMeta.name ? ` "${modalMeta.name}"` : '';
    headerLines.push(
      `[MODAL] [${modalMeta.ref}] ${modalMeta.role}${mNamePart} open — dismiss with Escape or close button`
    );
  }

  // Format under maxChars budget
  const lines: string[] = [...headerLines];
  let currentLen = headerLines.reduce((acc, l) => acc + l.length + 1, 0);
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

  const page = { url, title };
  const stateFingerprint = `${url}|${Math.round(scrollTop)}|${focusMeta?.ref || ''}|${modalMeta?.ref || ''}|${items.length}`;

  return {
    text: lines.join('\n'),
    generation: contentState.generation,
    page,
    observation_meta: {
      url,
      title,
      viewport: {
        scroll_pct: scrollPct,
        at_top: atTop,
        at_bottom: atBottom,
        screens_above: screensAbove,
        screens_below: screensBelow,
        can_scroll: canScroll,
        scrollable_containers: scrollableContainers,
      },
      focus: focusMeta,
      modal: modalMeta,
      state_fingerprint: stateFingerprint,
    },
  };
}
