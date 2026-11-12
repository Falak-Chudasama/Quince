import { BLOCKED_SCHEMES } from '../shared/constants.js';
import { BridgeError } from '../shared/errors.js';
import { TabInfo } from '../shared/types.js';
import { ensureQuinceGroup } from './group.js';
import { log } from './logger.js';
import { getSessionState, getSettings, updateSessionState } from './settings.js';

export function redactUrl(urlStr: string): string {
  try {
    const u = new URL(urlStr);
    const hasSensitive = /token|key|auth|session|code|secret|password|sig/i.test(u.search);
    if (urlStr.length > 80 || hasSensitive) {
      if (u.search) u.search = '?';
      if (u.hash) u.hash = '#';
    }
    return u.toString();
  } catch {
    return urlStr;
  }
}

export async function validateTargetUrl(urlStr: string): Promise<string> {
  let target = urlStr.trim();
  if (!target.includes('://')) {
    target = 'https://' + target;
  }

  let parsed: URL;
  try {
    parsed = new URL(target);
  } catch {
    throw new BridgeError('invalid_argument', `Malformed URL: ${urlStr}`);
  }

  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    const settings = await getSettings();
    if (parsed.protocol === 'file:' && settings.allowFileUrls) {
      // Allowed if explicitly enabled in settings
    } else {
      throw new BridgeError('blocked_target', `Scheme ${parsed.protocol} is not allowed.`, {
        data: { reason: 'blocked_scheme', scheme: parsed.protocol },
      });
    }
  }

  const settings = await getSettings();
  const host = parsed.hostname.toLowerCase();
  for (const b of settings.blockedHosts) {
    if (host === b.toLowerCase() || host.endsWith('.' + b.toLowerCase())) {
      throw new BridgeError('blocked_target', `Host ${host} is blocked by user settings.`, {
        data: { reason: 'blocked_host', host },
      });
    }
  }

  return target;
}

export async function isTabControlled(tabId: number): Promise<boolean> {
  const session = await getSessionState();
  return session.controlledTabIds.includes(tabId);
}

export async function adoptTab(tabId: number): Promise<void> {
  const session = await getSessionState();
  if (!session.controlledTabIds.includes(tabId)) {
    const newControlled = [...session.controlledTabIds, tabId];
    await updateSessionState({ controlledTabIds: newControlled });
  }
  await ensureQuinceGroup(tabId);
}

export async function releaseTab(tabId: number): Promise<void> {
  const session = await getSessionState();
  const newControlled = session.controlledTabIds.filter((id) => id !== tabId);
  await updateSessionState({ controlledTabIds: newControlled });
  try {
    await chrome.tabs.ungroup(tabId);
  } catch {}
}

export async function listTabs(): Promise<{ tabs: TabInfo[] }> {
  const allTabs = await chrome.tabs.query({});
  const session = await getSessionState();

  const formatted: TabInfo[] = allTabs.map((t) => ({
    tab_id: t.id!,
    title: (t.title || '').slice(0, 80),
    url: redactUrl(t.url || ''),
    active: t.active,
    controlled: session.controlledTabIds.includes(t.id!),
    audible: t.audible,
    pinned: t.pinned,
    window_id: t.windowId,
  }));

  // Sort controlled & active first
  formatted.sort((a, b) => {
    if (a.controlled && !b.controlled) return -1;
    if (!a.controlled && b.controlled) return 1;
    if (a.active && !b.active) return -1;
    if (!a.active && b.active) return 1;
    return 0;
  });

  return { tabs: formatted.slice(0, 40) };
}

export async function openTab(url: string, active: boolean = true): Promise<{ tab_id: number; url: string; title: string }> {
  const validated = await validateTargetUrl(url);
  const tab = await chrome.tabs.create({ url: validated, active });
  const tabId = tab.id!;

  await adoptTab(tabId);

  // Wait for tab to load status === 'complete'
  await new Promise<void>((resolve) => {
    const listener = (tid: number, changeInfo: chrome.tabs.TabChangeInfo) => {
      if (tid === tabId && changeInfo.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }, 10_000);
  });

  const updatedTab = await chrome.tabs.get(tabId);
  return {
    tab_id: tabId,
    url: redactUrl(updatedTab.url || validated),
    title: updatedTab.title || '',
  };
}

export async function switchTab(tabId: number): Promise<{ tab_id: number; url: string; title: string }> {
  const tab = await chrome.tabs.get(tabId).catch(() => null);
  if (!tab) {
    throw new BridgeError('tab_not_found', `Tab ${tabId} does not exist`);
  }

  await adoptTab(tabId);
  await chrome.tabs.update(tabId, { active: true });
  if (tab.windowId) {
    await chrome.windows.update(tab.windowId, { focused: true }).catch(() => {});
  }

  return {
    tab_id: tabId,
    url: redactUrl(tab.url || ''),
    title: tab.title || '',
  };
}

export async function useCurrentTab(): Promise<{ tab_id: number; url: string; title: string }> {
  const [activeTab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!activeTab || !activeTab.id) {
    throw new BridgeError('tab_not_found', 'No active tab found in current window');
  }

  // Validate scheme
  const url = activeTab.url || '';
  if (BLOCKED_SCHEMES.some((s) => url.startsWith(s)) && !url.startsWith('about:blank')) {
    throw new BridgeError('blocked_target', `Current tab has restricted URL: ${url}`);
  }

  await adoptTab(activeTab.id);
  return {
    tab_id: activeTab.id,
    url: redactUrl(url),
    title: activeTab.title || '',
  };
}

export async function closeTab(tabId: number): Promise<{ ok: boolean }> {
  const controlled = await isTabControlled(tabId);
  if (!controlled) {
    throw new BridgeError('tab_not_controlled', `Tab ${tabId} is not controlled by Quince`);
  }

  await releaseTab(tabId);
  await chrome.tabs.remove(tabId).catch(() => {});
  return { ok: true };
}

export async function navigateTab(
  tabId: number,
  action: 'goto' | 'back' | 'forward' | 'reload',
  url?: string
): Promise<{ ok: boolean }> {
  const controlled = await isTabControlled(tabId);
  if (!controlled) {
    throw new BridgeError('tab_not_controlled', `Tab ${tabId} is not controlled by Quince`);
  }

  if (action === 'goto') {
    if (!url) throw new BridgeError('invalid_argument', 'URL required for goto action');
    const validated = await validateTargetUrl(url);
    await chrome.tabs.update(tabId, { url: validated });
  } else if (action === 'back') {
    await chrome.tabs.goBack(tabId);
  } else if (action === 'forward') {
    await chrome.tabs.goForward(tabId);
  } else if (action === 'reload') {
    await chrome.tabs.reload(tabId);
  }

  return { ok: true };
}
