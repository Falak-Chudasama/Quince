import test from 'node:test';
import assert from 'node:assert/strict';
import esbuild from 'esbuild';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { installDomEnv } from './dom-shim.mjs';

const extRoot = path.resolve(import.meta.dirname, '..');
const tmpOut = fs.mkdtempSync(path.join(os.tmpdir(), 'quince-ext-test-'));

// Compile the real TypeScript source modules directly using esbuild with splitting=true
// so shared singletons (like contentState) share one module instance.
await esbuild.build({
  entryPoints: [
    path.join(extRoot, 'src/content/snapshot.ts'),
    path.join(extRoot, 'src/content/diff.ts'),
    path.join(extRoot, 'src/content/find.ts'),
    path.join(extRoot, 'src/content/redact.ts'),
    path.join(extRoot, 'src/content/state.ts'),
    path.join(extRoot, 'src/content/actions/type.ts'),
    path.join(extRoot, 'src/content/actions/click.ts'),
    path.join(extRoot, 'src/content/actions/scroll.ts'),
    path.join(extRoot, 'src/content/actions/key.ts'),
    path.join(extRoot, 'src/content/actions/select.ts'),
    path.join(extRoot, 'src/background/risk.ts'),
  ],
  outdir: tmpOut,
  outbase: path.join(extRoot, 'src'),
  bundle: true,
  splitting: true,
  format: 'esm',
  platform: 'neutral',
  target: 'es2022',
});

const importMod = (rel) => import(pathToFileURL(path.join(tmpOut, rel)).href);

const { generateSnapshot } = await importMod('content/snapshot.js');
const { captureState, computeStateChange } = await importMod('content/diff.js');
const { findInPage } = await importMod('content/find.js');
const { isSensitiveField, sanitizeValue } = await importMod('content/redact.js');
const { contentState } = await importMod('content/state.js');
const { executeType } = await importMod('content/actions/type.js');
const { executeClick } = await importMod('content/actions/click.js');
const { executeScroll } = await importMod('content/actions/scroll.js');
const { executePressKey } = await importMod('content/actions/key.js');
const { executeSelectOption } = await importMod('content/actions/select.js');
const { evaluateRisk, createConfirmationToken, validateAndConsumeToken } = await importMod('background/risk.js');

test('1. Controlled input type(clear=true, submit=true) clears, dispatches Enter, and falls back to form.requestSubmit', async () => {
  const env = installDomEnv({ url: 'https://www.amazon.com/', title: 'Amazon' });
  contentState.resetRefs();

  const form = new env.FakeFormElement({ role: 'search' });
  const input = new env.FakeInputElement({ type: 'search', placeholder: 'Search Amazon', value: 'old query' });
  const submitBtn = new env.FakeHTMLElement('button', { type: 'submit' });
  submitBtn.textContent = 'Go';
  form.appendChild(input);
  form.appendChild(submitBtn);
  env.body.appendChild(form);

  const ref = contentState.getOrCreateRef(input);
  const events = [];
  input.addEventListener('input', () => events.push(`input:${input.value}`));
  input.addEventListener('change', () => events.push(`change:${input.value}`));
  input.addEventListener('keydown', (e) => events.push(`keydown:${e.key}:${e.keyCode}`));
  input.addEventListener('keypress', (e) => events.push(`keypress:${e.key}:${e.keyCode}`));
  input.addEventListener('keyup', (e) => events.push(`keyup:${e.key}:${e.keyCode}`));

  await executeType(ref, 'wireless headphones', true, true);

  assert.equal(input.value, 'wireless headphones');
  assert.ok(events.includes('input:'), 'Should clear controlled value cleanly first');
  assert.ok(events.includes('input:wireless headphones'));
  assert.ok(events.includes('change:wireless headphones'));
  assert.ok(events.includes('keydown:Enter:13'));
  assert.ok(events.includes('keypress:Enter:13'));
  assert.ok(events.includes('keyup:Enter:13'));
  assert.equal(form.requestSubmitCount, 1, 'Should fall back to form.requestSubmit after 400ms without DOM mutation');
  assert.equal(form.lastSubmitter, submitBtn);
});

test('2. Viewport telemetry, semantic scroll(pages=0.8), container_ref scroll, and auto-scrollIntoView', () => {
  const env = installDomEnv({ url: 'https://example.com/list', title: 'Long List', innerHeight: 500, scrollHeight: 2000 });
  contentState.resetRefs();

  const heading = new env.FakeHTMLElement('h1');
  heading.textContent = 'Top Title';
  heading._rect = { left: 10, top: 20, right: 300, bottom: 60, width: 290, height: 40 };

  const sidebar = new env.FakeHTMLElement('div', { role: 'region', 'aria-label': 'Filters' });
  sidebar._style.overflowY = 'auto';
  sidebar.clientHeight = 250;
  sidebar.scrollHeight = 1000;
  sidebar._rect = { left: 10, top: 80, right: 200, bottom: 330, width: 190, height: 250 };

  const farButton = new env.FakeHTMLElement('button');
  farButton.textContent = 'Load More';
  farButton._rect = { left: 10, top: 1400, right: 150, bottom: 1440, width: 140, height: 40 };

  env.body.appendChild(heading);
  env.body.appendChild(sidebar);
  env.body.appendChild(farButton);

  // At top
  const snapTop = generateSnapshot();
  assert.match(snapTop.text, /\[VIEWPORT\] 0% AT TOP \| ~0\.0 above \| ~3\.0 below \| can_scroll: down/);
  assert.equal(snapTop.observation_meta.viewport.at_top, true);
  assert.equal(snapTop.observation_meta.viewport.at_bottom, false);
  const sidebarRef = snapTop.observation_meta.viewport.scrollable_containers[0].ref;

  // Semantic scroll down 0.8 pages (0.8 * 500 = 400px)
  executeScroll({ direction: 'down', pages: 0.8 });
  assert.equal(env.win.scrollY, 400);

  // Scroll inside container_ref
  executeScroll({ direction: 'down', pages: 0.8, container_ref: sidebarRef });
  assert.equal(sidebar.scrollTop, 200);

  // Scroll to bottom
  executeScroll({ direction: 'bottom' });
  const snapBottom = generateSnapshot();
  assert.match(snapBottom.text, /\[VIEWPORT\] 100% AT BOTTOM/);
  assert.deepEqual(snapBottom.observation_meta.viewport.can_scroll, ['up']);

  // Auto-scroll offscreen target into view on click
  env.win.scrollTo({ top: 0 });
  const farRef = contentState.getOrCreateRef(farButton);
  let clicked = false;
  farButton.addEventListener('click', () => { clicked = true; });
  executeClick(farRef);
  assert.ok(farButton.scrollIntoViewCalls.length >= 1);
  assert.equal(clicked, true);
});

test('3. Modal hoisting, autocomplete role="listbox" DOM_UPDATED diff, and Escape dismissal', async () => {
  const env = installDomEnv({ url: 'https://shop.example.com/', title: 'Shop' });
  contentState.resetRefs();

  const searchInput = new env.FakeInputElement({ type: 'search', 'aria-label': 'Search' });
  const bgBtn = new env.FakeHTMLElement('button');
  bgBtn.textContent = 'Background Action';
  const modal = new env.FakeHTMLElement('div', { role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Cookie Consent' });
  const acceptBtn = new env.FakeHTMLElement('button');
  acceptBtn.textContent = 'Accept Cookies';
  modal.appendChild(acceptBtn);

  env.body.appendChild(searchInput);
  env.body.appendChild(bgBtn);
  env.body.appendChild(modal);

  // Escape closes modal
  modal.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      modal._style.display = 'none';
    }
  });

  const snapWithModal = generateSnapshot();
  assert.match(snapWithModal.text, /\[MODAL\] \[e\d+\] dialog "Cookie Consent" open — dismiss with Escape or close button/);
  const acceptLineIdx = snapWithModal.text.indexOf('Accept Cookies');
  const bgLineIdx = snapWithModal.text.indexOf('Background Action');
  assert.ok(acceptLineIdx < bgLineIdx, 'Modal interactive elements must be hoisted above background elements');

  // Dismiss modal with Escape
  const preEsc = captureState();
  const acceptRef = contentState.getOrCreateRef(acceptBtn);
  await executePressKey('Escape', acceptRef);
  const postEsc = captureState();
  const escDiff = computeStateChange(preEsc, postEsc, { settled: true, reason: 'quiet', elapsed_ms: 50 });
  assert.equal(escDiff.causal_outcome, 'DOM_UPDATED');

  // Autocomplete listbox appears
  const preAc = captureState();
  const listbox = new env.FakeHTMLElement('ul', { role: 'listbox', 'aria-label': 'Suggestions' });
  const opt1 = new env.FakeHTMLElement('li', { role: 'option' });
  opt1.textContent = 'headphones sony';
  listbox.appendChild(opt1);
  env.body.appendChild(listbox);
  const postAc = captureState();
  const acDiff = computeStateChange(preAc, postAc, { settled: true, reason: 'quiet', elapsed_ms: 60 });
  assert.equal(acDiff.causal_outcome, 'DOM_UPDATED');
  assert.equal(acDiff.autocomplete_appeared, true);
});

test('4. Directional findInPage reports in_viewport, above_viewport, and below_viewport counts', () => {
  const env = installDomEnv({ innerHeight: 500, scrollHeight: 2000 });
  contentState.resetRefs();
  env.win.scrollY = 500; // viewport covers [500, 1000]

  const above = new env.FakeHTMLElement('button');
  above.textContent = 'Deal Above';
  above._rect = { left: 10, top: 100, right: 120, bottom: 140, width: 110, height: 40 };

  const inside = new env.FakeHTMLElement('button');
  inside.textContent = 'Deal Inside';
  inside._rect = { left: 10, top: 600, right: 120, bottom: 640, width: 110, height: 40 };

  const below1 = new env.FakeHTMLElement('button');
  below1.textContent = 'Deal Below 1';
  below1._rect = { left: 10, top: 1200, right: 120, bottom: 1240, width: 110, height: 40 };

  const below2 = new env.FakeHTMLElement('button');
  below2.textContent = 'Deal Below 2';
  below2._rect = { left: 10, top: 1500, right: 120, bottom: 1540, width: 110, height: 40 };

  env.body.appendChild(above);
  env.body.appendChild(inside);
  env.body.appendChild(below1);
  env.body.appendChild(below2);

  const res = findInPage('Deal', 10);
  assert.deepEqual(res.counts, {
    total: 4,
    in_viewport: 1,
    above_viewport: 1,
    below_viewport: 2,
  });
  const positions = Object.fromEntries(res.results.map((r) => [r.name, r.position]));
  assert.equal(positions['Deal Above'], 'above');
  assert.equal(positions['Deal Inside'], 'in_viewport');
  assert.equal(positions['Deal Below 1'], 'below');
});

test('5. Sensitive data redaction blocks typing and redacts password, OTP, CVV, and card values', async () => {
  const env = installDomEnv();
  contentState.resetRefs();

  const pw = new env.FakeInputElement({ type: 'password', value: 'my-secret-pw' });
  const otp = new env.FakeInputElement({ type: 'text', autocomplete: 'one-time-code', value: '998877' });
  const cc = new env.FakeInputElement({ type: 'text', autocomplete: 'cc-number', value: '4111222233334444' });
  const cvv = new env.FakeInputElement({ type: 'text', name: 'card_cvv', value: '123' });
  const tok = new env.FakeInputElement({ type: 'text', name: 'api_token', value: 'sk-secret-tok-999' });

  env.body.appendChild(pw);
  env.body.appendChild(otp);
  env.body.appendChild(cc);
  env.body.appendChild(cvv);
  env.body.appendChild(tok);

  for (const el of [pw, otp, cc, cvv, tok]) {
    assert.equal(isSensitiveField(el), true);
    assert.equal(sanitizeValue(el, el.value), '[REDACTED]');
    const ref = contentState.getOrCreateRef(el);
    await assert.rejects(() => executeType(ref, '1234', true, false), /sensitive|password/i);
  }

  const snap = generateSnapshot();
  assert.equal(snap.text.includes('my-secret-pw'), false);
  assert.equal(snap.text.includes('998877'), false);
  assert.equal(snap.text.includes('4111222233334444'), false);
  assert.equal(snap.text.includes('123'), false);
  assert.equal(snap.text.includes('sk-secret-tok-999'), false);
});

test('6. Risk gate flags irreversible actions and enforces single-use confirmation tokens', async () => {
  const localStore = new Map();
  const sessionStore = new Map();
  const mockGet = (store) => async (keys) => {
    if (typeof keys === 'string') return { [keys]: store.get(keys) };
    if (Array.isArray(keys)) return Object.fromEntries(keys.map((k) => [k, store.get(k)]));
    if (keys && typeof keys === 'object') {
      const out = { ...keys };
      for (const k of Object.keys(keys)) {
        if (store.has(k)) out[k] = store.get(k);
      }
      return out;
    }
    return Object.fromEntries(store.entries());
  };
  globalThis.chrome = {
    storage: {
      local: {
        get: mockGet(localStore),
        set: async (obj) => {
          for (const [k, v] of Object.entries(obj)) localStore.set(k, v);
        },
      },
      session: {
        get: mockGet(sessionStore),
        set: async (obj) => {
          for (const [k, v] of Object.entries(obj)) sessionStore.set(k, v);
        },
        remove: async (k) => { sessionStore.delete(k); },
      },
    },
  };

  const riskHigh = await evaluateRisk(1, 'e9', 'act.click', {
    name: 'Place Order',
    host: 'shop.example.com',
  });
  assert.equal(riskHigh.level, 'high');

  const riskLow = await evaluateRisk(1, 'e2', 'act.click', {
    name: 'Next Page',
    host: 'shop.example.com',
  });
  assert.equal(riskLow.level, 'low');

  const token = await createConfirmationToken(1, 'e9', 'act.click');
  assert.equal(await validateAndConsumeToken(token, 1, 'e8', 'act.click'), false, 'Mismatch must fail and consume');
  const token2 = await createConfirmationToken(1, 'e9', 'act.click');
  assert.equal(await validateAndConsumeToken(token2, 1, 'e9', 'act.click'), true);
  assert.equal(await validateAndConsumeToken(token2, 1, 'e9', 'act.click'), false, 'Replay must fail');
});
