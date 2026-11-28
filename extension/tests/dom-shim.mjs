// Lightweight, faithful DOM & browser API shim for testing extension TypeScript modules in Node.

export function installDomEnv(options = {}) {
  const listeners = new WeakMap();

  class FakeEvent {
    constructor(type, init = {}) {
      this.type = type;
      this.bubbles = Boolean(init.bubbles);
      this.cancelable = Boolean(init.cancelable);
      this.defaultPrevented = false;
      this.target = null;
      this.currentTarget = null;
      this._stopped = false;
    }
    preventDefault() {
      if (this.cancelable) this.defaultPrevented = true;
    }
    stopPropagation() {
      this._stopped = true;
    }
  }

  class FakeKeyboardEvent extends FakeEvent {
    constructor(type, init = {}) {
      super(type, init);
      this.key = init.key || '';
      this.code = init.code || '';
      this.keyCode = init.keyCode || 0;
      this.which = init.which || init.keyCode || 0;
      this.charCode = init.charCode || 0;
      this.ctrlKey = Boolean(init.ctrlKey);
      this.shiftKey = Boolean(init.shiftKey);
      this.altKey = Boolean(init.altKey);
      this.metaKey = Boolean(init.metaKey);
    }
  }

  class FakeMouseEvent extends FakeEvent {
    constructor(type, init = {}) {
      super(type, init);
      this.clientX = init.clientX || 0;
      this.clientY = init.clientY || 0;
      this.button = init.button || 0;
    }
  }

  const observers = new Set();
  function notifyObservers(mutation) {
    for (const obs of observers) {
      obs._queue(mutation);
    }
  }

  class FakeMutationObserver {
    constructor(cb) {
      this._cb = cb;
      this._observed = false;
    }
    observe() {
      this._observed = true;
      observers.add(this);
    }
    disconnect() {
      this._observed = false;
      observers.delete(this);
    }
    _queue(m) {
      if (this._observed) {
        this._cb([m], this);
      }
    }
  }

  class FakeClassList {
    constructor(el) {
      this._el = el;
    }
    _set() {
      return new Set((this._el.getAttribute('class') || '').split(/\s+/).filter(Boolean));
    }
    contains(cls) {
      return this._set().has(cls);
    }
    add(cls) {
      const s = this._set();
      s.add(cls);
      this._el.setAttribute('class', Array.from(s).join(' '));
    }
    remove(cls) {
      const s = this._set();
      s.delete(cls);
      this._el.setAttribute('class', Array.from(s).join(' '));
    }
  }

  class FakeElement {
    constructor(tagName, attrs = {}) {
      this.tagName = tagName.toUpperCase();
      this.nodeType = 1;
      this._attrs = new Map();
      this._children = [];
      this.parentElement = null;
      this.parentNode = null;
      this.shadowRoot = null;
      this.hidden = false;
      this.scrollTop = 0;
      this.scrollHeight = 100;
      this.clientHeight = 100;
      this.scrollWidth = 100;
      this.clientWidth = 100;
      this._style = { display: 'block', visibility: 'visible', opacity: '1', overflowY: 'visible' };
      this._rect = { left: 10, top: 10, right: 110, bottom: 40, width: 100, height: 30 };
      this._textContent = '';
      this.isContentEditable = false;
      this.scrollIntoViewCalls = [];
      this.classList = new FakeClassList(this);
      for (const [k, v] of Object.entries(attrs)) {
        this.setAttribute(k, String(v));
      }
    }
    get id() { return this.getAttribute('id') || ''; }
    set id(v) { this.setAttribute('id', v); }
    get children() { return this._children; }
    get childNodes() { return this._children; }
    get textContent() {
      if (this._children.length === 0) return this._textContent;
      return this._textContent + this._children.map((c) => c.textContent).join(' ');
    }
    set textContent(val) {
      this._textContent = String(val ?? '');
    }
    hasAttribute(name) { return this._attrs.has(name.toLowerCase()); }
    getAttribute(name) {
      const v = this._attrs.get(name.toLowerCase());
      return v === undefined ? null : v;
    }
    setAttribute(name, val) {
      const key = name.toLowerCase();
      this._attrs.set(key, String(val));
      if (key === 'hidden') this.hidden = true;
      notifyObservers({ type: 'attributes', target: this, attributeName: key });
    }
    removeAttribute(name) {
      const key = name.toLowerCase();
      this._attrs.delete(key);
      if (key === 'hidden') this.hidden = false;
      notifyObservers({ type: 'attributes', target: this, attributeName: key });
    }
    appendChild(child) {
      child.parentElement = this;
      child.parentNode = this;
      this._children.push(child);
      notifyObservers({ type: 'childList', target: this, addedNodes: [child], removedNodes: [] });
      return child;
    }
    removeChild(child) {
      const idx = this._children.indexOf(child);
      if (idx >= 0) {
        this._children.splice(idx, 1);
        child.parentElement = null;
        child.parentNode = null;
        notifyObservers({ type: 'childList', target: this, addedNodes: [], removedNodes: [child] });
      }
      return child;
    }
    contains(other) {
      let cur = other;
      while (cur) {
        if (cur === this) return true;
        cur = cur.parentElement;
      }
      return false;
    }
    closest(selector) {
      const parts = selector.split(',').map((s) => s.trim());
      let cur = this;
      while (cur) {
        if (parts.some((p) => matchesSimpleSelector(cur, p))) return cur;
        cur = cur.parentElement;
      }
      return null;
    }
    querySelectorAll(selector) {
      const parts = selector.split(',').map((s) => s.trim());
      const out = [];
      const walk = (node) => {
        for (const c of node._children) {
          if (parts.some((p) => matchesSimpleSelector(c, p))) out.push(c);
          walk(c);
        }
      };
      walk(this);
      return out;
    }
    querySelector(selector) {
      return this.querySelectorAll(selector)[0] || null;
    }
    getBoundingClientRect() {
      // Shift by window scrollY if element is in document flow (unless fixed)
      const sy = this._fixed ? 0 : (globalThis.window?.scrollY || 0);
      return {
        left: this._rect.left,
        top: this._rect.top - sy,
        right: this._rect.right,
        bottom: this._rect.bottom - sy,
        width: this._rect.width,
        height: this._rect.height,
      };
    }
    scrollIntoView(arg) {
      this.scrollIntoViewCalls.push(arg);
      // Center in viewport
      const vh = globalThis.window.innerHeight;
      if (this._rect.bottom - globalThis.window.scrollY > vh || this._rect.top - globalThis.window.scrollY < 0) {
        globalThis.window.scrollY = Math.max(0, this._rect.top - vh / 2);
        globalThis.document.documentElement.scrollTop = globalThis.window.scrollY;
      }
    }
    addEventListener(type, fn) {
      let map = listeners.get(this);
      if (!map) { map = new Map(); listeners.set(this, map); }
      if (!map.has(type)) map.set(type, []);
      map.get(type).push(fn);
    }
    dispatchEvent(evt) {
      evt.target = this;
      let cur = this;
      while (cur && !evt._stopped) {
        evt.currentTarget = cur;
        const map = listeners.get(cur);
        const fns = map?.get(evt.type) || [];
        for (const fn of fns) fn(evt);
        if (!evt.bubbles) break;
        cur = cur.parentElement || (cur === globalThis.document.documentElement ? null : null);
      }
      return !evt.defaultPrevented;
    }
    focus() {
      globalThis.document.activeElement = this;
    }
    click() {
      this.dispatchEvent(new FakeMouseEvent('click', { bubbles: true, cancelable: true }));
    }
  }

  class FakeHTMLElement extends FakeElement {}

  class FakeInputElement extends FakeHTMLElement {
    constructor(attrs = {}) {
      super('input', attrs);
      this._value = attrs.value || '';
      this.checked = Boolean(attrs.checked);
      this.selected = false;
    }
    get type() { return (this.getAttribute('type') || 'text').toLowerCase(); }
    set type(v) { this.setAttribute('type', v); }
    get name() { return this.getAttribute('name') || ''; }
    get placeholder() { return this.getAttribute('placeholder') || ''; }
    get autocomplete() { return this.getAttribute('autocomplete') || ''; }
    get form() { return this.closest('form'); }
    get value() { return this._value; }
    set value(v) { this._value = String(v ?? ''); }
    select() { this.selected = true; }
  }

  class FakeTextAreaElement extends FakeHTMLElement {
    constructor(attrs = {}) {
      super('textarea', attrs);
      this._value = attrs.value || '';
    }
    get placeholder() { return this.getAttribute('placeholder') || ''; }
    get value() { return this._value; }
    set value(v) { this._value = String(v ?? ''); }
    select() {}
  }

  class FakeSelectElement extends FakeHTMLElement {
    constructor(attrs = {}) {
      super('select', attrs);
      this.options = [];
      this.selectedIndex = 0;
      this.multiple = false;
    }
    get selectedOptions() {
      return this.options[this.selectedIndex] ? [this.options[this.selectedIndex]] : [];
    }
    get value() {
      return this.options[this.selectedIndex]?.value || '';
    }
  }

  class FakeFormElement extends FakeHTMLElement {
    constructor(attrs = {}) {
      super('form', attrs);
      this.requestSubmitCount = 0;
      this.submitCount = 0;
      this.lastSubmitter = null;
    }
    requestSubmit(submitter) {
      this.requestSubmitCount++;
      this.lastSubmitter = submitter || null;
      this.dispatchEvent(new FakeEvent('submit', { bubbles: true, cancelable: true }));
    }
    submit() {
      this.submitCount++;
    }
  }

  function matchesSimpleSelector(el, sel) {
    if (!sel) return false;
    if (sel.startsWith('[')) {
      const m = sel.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
      if (m) {
        const attr = m[1].toLowerCase();
        const val = m[2];
        if (val !== undefined) return el.getAttribute(attr) === val;
        return el.hasAttribute(attr);
      }
    }
    if (sel === 'dialog[open]') return el.tagName === 'DIALOG' && el.hasAttribute('open');
    if (sel.startsWith('button[type="submit"]')) {
      return el.tagName === 'BUTTON' && el.getAttribute('type') === 'submit' && !el.hasAttribute('disabled');
    }
    if (sel.startsWith('input[type="submit"]')) {
      return el.tagName === 'INPUT' && el.getAttribute('type') === 'submit' && !el.hasAttribute('disabled');
    }
    if (sel.startsWith('button:not([type])')) {
      return el.tagName === 'BUTTON' && !el.hasAttribute('type') && !el.hasAttribute('disabled');
    }
    if (sel.startsWith('input:not([type="hidden"])')) {
      return el.tagName === 'INPUT' && el.getAttribute('type') !== 'hidden';
    }
    if (sel.startsWith('label[for="')) {
      const id = sel.slice(11, -2);
      return el.tagName === 'LABEL' && el.getAttribute('for') === id;
    }
    return el.tagName.toLowerCase() === sel.toLowerCase();
  }

  const html = new FakeHTMLElement('html');
  const body = new FakeHTMLElement('body');
  html.appendChild(body);
  html.scrollHeight = options.scrollHeight || 800;
  body.scrollHeight = options.scrollHeight || 800;

  const doc = {
    documentElement: html,
    body,
    title: options.title || 'Test Page',
    activeElement: body,
    getElementById(id) {
      return html.querySelector(`[id="${id}"]`);
    },
    querySelector(sel) {
      return html.querySelector(sel);
    },
    querySelectorAll(sel) {
      return html.querySelectorAll(sel);
    },
    elementFromPoint(x, y) {
      // Find topmost visible child whose rect contains (x, y)
      let hit = null;
      const walk = (node) => {
        for (const c of node._children) {
          if (!c.hidden && c._style.display !== 'none' && c._style.visibility !== 'hidden') {
            const r = c.getBoundingClientRect();
            if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom && r.width > 0 && r.height > 0) {
              hit = c;
            }
            walk(c);
          }
        }
      };
      walk(body);
      return hit;
    },
    createTreeWalker(root, _what, filter) {
      const list = [];
      const walk = (node) => {
        for (const c of node._children) {
          const decision = filter ? filter.acceptNode(c) : 1;
          if (decision === 1) {
            list.push(c);
            walk(c);
          }
          // decision === 2 (FILTER_REJECT) skips subtree
        }
      };
      walk(root);
      let idx = 0;
      return {
        nextNode() {
          return idx < list.length ? list[idx++] : null;
        },
      };
    },
  };

  const win = {
    innerHeight: options.innerHeight || 800,
    innerWidth: options.innerWidth || 1280,
    scrollY: 0,
    location: { href: options.url || 'https://example.com/', host: 'example.com' },
    getComputedStyle(el) {
      return el._style;
    },
    scrollTo(opts) {
      const max = Math.max(0, html.scrollHeight - win.innerHeight);
      win.scrollY = Math.max(0, Math.min(max, opts.top ?? 0));
      html.scrollTop = win.scrollY;
    },
    scrollBy(opts) {
      const max = Math.max(0, html.scrollHeight - win.innerHeight);
      win.scrollY = Math.max(0, Math.min(max, win.scrollY + (opts.top ?? 0)));
      html.scrollTop = win.scrollY;
    },
  };

  globalThis.window = win;
  globalThis.document = doc;
  globalThis.Element = FakeElement;
  globalThis.HTMLElement = FakeHTMLElement;
  globalThis.HTMLInputElement = FakeInputElement;
  globalThis.HTMLTextAreaElement = FakeTextAreaElement;
  globalThis.HTMLSelectElement = FakeSelectElement;
  globalThis.HTMLFormElement = FakeFormElement;
  globalThis.HTMLImageElement = class extends FakeHTMLElement {};
  globalThis.Event = FakeEvent;
  globalThis.KeyboardEvent = FakeKeyboardEvent;
  globalThis.MouseEvent = FakeMouseEvent;
  globalThis.MutationObserver = FakeMutationObserver;
  globalThis.NodeFilter = { SHOW_ELEMENT: 1, FILTER_ACCEPT: 1, FILTER_REJECT: 2, FILTER_SKIP: 3 };
  globalThis.CSS = { escape: (s) => s };

  return {
    win,
    doc,
    body,
    html,
    FakeElement,
    FakeHTMLElement,
    FakeInputElement,
    FakeTextAreaElement,
    FakeSelectElement,
    FakeFormElement,
  };
}
