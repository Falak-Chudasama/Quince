import { executeSetChecked, executeHover } from './actions/checked.js';
import { executeClick } from './actions/click.js';
import { executeFillForm } from './actions/form.js';
import { executePressKey } from './actions/key.js';
import { executeScroll } from './actions/scroll.js';
import { executeSelectOption } from './actions/select.js';
import { executeType } from './actions/type.js';
import { getAccessibleName } from './accname.js';
import { captureState, computeStateChange } from './diff.js';
import { findInPage, readText } from './find.js';
import { setOverlayActive } from './overlay.js';
import { isSensitiveField } from './redact.js';
import { getElementRole } from './roles.js';
import { generateSnapshot } from './snapshot.js';
import { contentState } from './state.js';
import { waitForDomQuiet } from './wait.js';

let lastScriptDialog: any = null;

// Listen to main-world dialog interceptor
window.addEventListener('__quince_script_dialog', (evt: any) => {
  lastScriptDialog = evt.detail;
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'ping') {
    sendResponse({ type: 'pong' });
    return false;
  }

  if (msg.type === 'set_indicator') {
    setOverlayActive(Boolean(msg.active));
    sendResponse({ ok: true });
    return false;
  }

  if (msg.method === 'inspect_target') {
    const el = contentState.getElement(msg.params.ref);
    if (!el) {
      sendResponse({ error: { code: 'not_found', message: `Ref ${msg.params.ref} not found` } });
      return false;
    }

    const name = getAccessibleName(el);
    const role = getElementRole(el);
    const tag = el.tagName.toLowerCase();
    const isSubmit = (el instanceof HTMLInputElement && el.type === 'submit') || (tag === 'button' && (el as HTMLButtonElement).type === 'submit');

    const form = el.closest('form');
    let hasSensitiveForm = false;
    if (form) {
      const inputs = form.querySelectorAll('input');
      for (const inp of Array.from(inputs)) {
        if (isSensitiveField(inp)) {
          hasSensitiveForm = true;
          break;
        }
      }
    }

    sendResponse({
      result: {
        name,
        role,
        tag,
        host: window.location.host,
        isSubmit,
        hasSensitiveForm,
      },
    });
    return false;
  }

  if (msg.type === 'method_call') {
    handleMethodCall(msg.method, msg.params)
      .then((res) => sendResponse({ result: res }))
      .catch((err) =>
        sendResponse({
          error: {
            code: err.code || 'execution_error',
            message: err.message || 'Error executing action',
            data: err.data || {},
          },
        })
      );
    return true; // Keep channel open for async response
  }
});

async function handleMethodCall(method: string, params: any): Promise<any> {
  // Reads
  if (method === 'page.snapshot') {
    return generateSnapshot(params);
  }
  if (method === 'page.find') {
    return findInPage(params.query, params.max_results);
  }
  if (method === 'page.read_text') {
    return readText(params.ref, params.max_chars);
  }

  // Pre-action capture
  const pre = captureState();

  // Execute action
  switch (method) {
    case 'act.click':
      executeClick(params.ref, params.click_type);
      break;
    case 'act.type':
      executeType(params.ref, params.text, params.clear_first, params.press_enter);
      break;
    case 'act.press_key':
      executePressKey(params.key, params.ref);
      break;
    case 'act.scroll':
      executeScroll(params.direction, params.ref);
      break;
    case 'act.select':
      executeSelectOption(params.ref, params.option);
      break;
    case 'act.set_checked':
      executeSetChecked(params.ref, params.checked);
      break;
    case 'act.hover':
      executeHover(params.ref);
      break;
    case 'act.fill_form':
      executeFillForm(params.refs, params.values);
      break;
    case 'act.wait':
      await new Promise((r) => setTimeout(r, (params.seconds || 3) * 1000));
      break;
    case 'tabs.navigate':
      // Navigation initiated in background
      break;
    default:
      throw new Error(`Unknown action: ${method}`);
  }

  // Post-action wait
  const quietMs = ['act.scroll', 'act.hover', 'act.press_key'].includes(method) ? 150 : 300;
  const waitInfo = await waitForDomQuiet(quietMs, 4000);

  // Post-action capture
  const post = captureState();
  const stateChange = computeStateChange(pre, post, waitInfo);

  if (lastScriptDialog) {
    stateChange.dialog = { script_dialog: lastScriptDialog };
    lastScriptDialog = null;
  }

  return { state_change: stateChange };
}
