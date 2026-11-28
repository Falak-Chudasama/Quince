import { BridgeError } from '../shared/errors.js';
import { ensureInjected } from './inject.js';
import { log } from './logger.js';
import { waitForNetIdle } from './net-idle.js';
import { createConfirmationToken, evaluateRisk, validateAndConsumeToken } from './risk.js';
import { beginSession, endSession } from './session.js';
import { getSessionState } from './settings.js';
import {
  closeTab,
  isTabControlled,
  listTabs,
  navigateTab,
  openTab,
  switchTab,
  useCurrentTab,
} from './tabs.js';

type MethodHandler = (params: any) => Promise<any>;

const handlers: Record<string, MethodHandler> = {
  // Session
  'session.begin': async (params) => {
    await beginSession(params.session_id);
    return { ok: true };
  },
  'session.end': async (params) => {
    await endSession(params.session_id, params.outcome);
    return { ok: true };
  },
  'bridge.status': async () => {
    const s = await getSessionState();
    return {
      status: 'ok',
      active_session_id: s.activeSessionId,
      controlled_tabs: s.controlledTabIds,
      paused: s.paused,
    };
  },

  // Tabs
  'tabs.list': async () => {
    return await listTabs();
  },
  'tabs.open': async (params) => {
    return await openTab(params.url, params.active ?? true);
  },
  'tabs.switch': async (params) => {
    return await switchTab(params.tab_id);
  },
  'tabs.use_current': async () => {
    return await useCurrentTab();
  },
  'tabs.close': async (params) => {
    return await closeTab(params.tab_id);
  },
  'tabs.navigate': async (params) => {
    await navigateTab(params.tab_id, params.action, params.url);
    // Wait for settle
    await waitForNetIdle(params.tab_id, 300, 5000);
    // Content script state change
    return await forwardToContent(params.tab_id, 'tabs.navigate', params);
  },

  // Page reads
  'page.snapshot': async (params) => {
    return await executeContentRead(params.tab_id, 'page.snapshot', params);
  },
  'page.find': async (params) => {
    return await executeContentRead(params.tab_id, 'page.find', params);
  },
  'page.read_text': async (params) => {
    return await executeContentRead(params.tab_id, 'page.read_text', params);
  },

  // Actions
  'act.click': async (params) => executeAction(params.tab_id, 'act.click', params),
  'act.type': async (params) => executeAction(params.tab_id, 'act.type', params),
  'act.press_key': async (params) => executeAction(params.tab_id, 'act.press_key', params),
  'act.scroll': async (params) => executeAction(params.tab_id, 'act.scroll', params),
  'act.select': async (params) => executeAction(params.tab_id, 'act.select', params),
  'act.set_checked': async (params) => executeAction(params.tab_id, 'act.set_checked', params),
  'act.hover': async (params) => executeAction(params.tab_id, 'act.hover', params),
  'act.fill_form': async (params) => executeAction(params.tab_id, 'act.fill_form', params),
  'act.wait': async (params) => executeAction(params.tab_id, 'act.wait', params),
};

async function executeContentRead(tabId: number, method: string, params: any): Promise<any> {
  const controlled = await isTabControlled(tabId);
  if (!controlled) {
    throw new BridgeError('tab_not_controlled', `Tab ${tabId} is not controlled by Quince`);
  }
  await ensureInjected(tabId);
  return await forwardToContent(tabId, method, params);
}

async function waitForTabComplete(tabId: number, maxMs: number = 3000): Promise<void> {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === 'complete') return;
  } catch {
    return;
  }

  await new Promise<void>((resolve) => {
    const listener = (tid: number, changeInfo: chrome.tabs.TabChangeInfo) => {
      if (tid === tabId && changeInfo.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        clearTimeout(timer);
        resolve();
      }
    };
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }, maxMs);
    chrome.tabs.onUpdated.addListener(listener);
  });
}

function isMutatingSettleAction(method: string, params: any): boolean {
  if (method === 'act.click' || method === 'act.select') return true;
  if (method === 'act.type' && Boolean(params.submit ?? params.press_enter)) return true;
  if (method === 'act.press_key' && String(params.key || '').toLowerCase() === 'enter') return true;
  return false;
}

async function buildNavigationStateChange(
  tabId: number,
  preUrl: string,
  preTitle: string,
  elapsedMs: number
): Promise<any> {
  await waitForTabComplete(tabId, 3000);
  await waitForNetIdle(tabId, 250, 1000);
  try {
    await ensureInjected(tabId);
  } catch {}
  const newTab = await chrome.tabs.get(tabId).catch(() => null);
  const afterUrl = newTab?.url || preUrl;
  const afterTitle = newTab?.title || '';
  const navigated = afterUrl !== preUrl;

  return {
    state_change: {
      effect: navigated ? 'navigated' : 'dom_changed',
      causal_outcome: navigated ? 'NAVIGATED' : 'DOM_UPDATED',
      summary_line: navigated
        ? `OUTCOME: NAVIGATED | Navigated to ${afterTitle || afterUrl}`
        : 'OUTCOME: DOM_UPDATED | Page reloaded',
      before: { url: preUrl, title: preTitle },
      after: { url: afterUrl, title: afterTitle },
      navigated,
      navigation_kind: 'full',
      dom: { added: [], removed: [], changed: [] },
      messages: [],
      no_visible_change: false,
      wait: { settled: true, reason: 'navigation_complete', elapsed_ms: elapsedMs },
    },
  };
}

async function executeAction(tabId: number, method: string, params: any): Promise<any> {
  const s = await getSessionState();
  if (s.paused) {
    throw new BridgeError('paused_by_user', 'Quince is currently paused by the user.');
  }

  const controlled = await isTabControlled(tabId);
  if (!controlled) {
    throw new BridgeError('tab_not_controlled', `Tab ${tabId} is not controlled by Quince`);
  }

  await ensureInjected(tabId);

  // Risk Gate evaluation for actions that modify or submit state
  const isGatedAction = ['act.click', 'act.type', 'act.press_key', 'act.set_checked'].includes(method);
  if (isGatedAction && params.ref) {
    const targetInfo = await forwardToContent(tabId, 'inspect_target', { ref: params.ref });
    const risk = await evaluateRisk(tabId, params.ref, method, targetInfo);

    if (risk.level === 'high') {
      const confirmToken = params.confirm_token;
      const valid = await validateAndConsumeToken(confirmToken, tabId, params.ref, method);
      if (!valid) {
        const pendingToken = await createConfirmationToken(tabId, params.ref, method);
        throw new BridgeError('confirmation_required', 'Action requires user confirmation', {
          data: {
            action: {
              level: 'high',
              reason: risk.reason,
              ref: params.ref,
              name: risk.name,
              host: risk.host,
              tool: method,
            },
            pending_token: pendingToken,
          },
        });
      }
    }
  }

  const preTab = await chrome.tabs.get(tabId).catch(() => null);
  const preUrl = preTab?.url || '';
  const preTitle = preTab?.title || '';
  const shouldSettle = isMutatingSettleAction(method, params);
  const startTime = Date.now();

  let res: any;
  try {
    res = await forwardToContent(tabId, method, shouldSettle ? { ...params, defer_capture: true } : params);
  } catch (err: any) {
    // If action triggered immediate full-page unload before response returned, recover gracefully
    if (shouldSettle && (err?.code === 'content_script_error' || err?.code === 'content_script_timeout')) {
      return await buildNavigationStateChange(tabId, preUrl, preTitle, Date.now() - startTime);
    }
    throw err;
  }

  if (res?.deferred) {
    await waitForNetIdle(tabId, 250, 1200);
    try {
      return await forwardToContent(tabId, 'act.finish_diff', {});
    } catch (err: any) {
      if (err?.code === 'content_script_error' || err?.code === 'content_script_timeout') {
        return await buildNavigationStateChange(
          tabId,
          res.pre_url || preUrl,
          res.pre_title || preTitle,
          Date.now() - startTime
        );
      }
      throw err;
    }
  }

  return res;
}

function forwardToContent(tabId: number, method: string, params: any): Promise<any> {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, { type: 'method_call', method, params }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new BridgeError('content_script_error', chrome.runtime.lastError.message));
        return;
      }
      if (!response) {
        reject(new BridgeError('content_script_timeout', 'No response from content script'));
        return;
      }
      if (response.error) {
        reject(new BridgeError(response.error.code, response.error.message, { data: response.error.data }));
      } else {
        resolve(response.result);
      }
    });
  });
}

export async function handleRequest(method: string, params: any): Promise<any> {
  const handler = handlers[method];
  if (!handler) {
    throw new BridgeError('unknown_method', `Unknown bridge method: ${method}`);
  }
  return await handler(params);
}
