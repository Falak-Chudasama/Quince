import { log } from './logger.js';

interface InFlightRequest {
  startTime: number;
}

const tabRequests = new Map<number, Map<string, InFlightRequest>>();

export function setupNetIdleTracking(): void {
  chrome.webRequest.onBeforeRequest.addListener(
    (details) => {
      if (details.tabId <= 0) return;
      // Skip web sockets, pings, or other long-lived types
      if (details.type === 'websocket' || details.type === 'ping' || details.type === 'other') {
        return;
      }

      let reqs = tabRequests.get(details.tabId);
      if (!reqs) {
        reqs = new Map();
        tabRequests.set(details.tabId, reqs);
      }
      reqs.set(details.requestId, { startTime: Date.now() });
    },
    { urls: ['http://*/*', 'https://*/*'] }
  );

  const cleanupRequest = (details: chrome.webRequest.WebResponseCacheDetails | chrome.webRequest.WebResponseErrorDetails) => {
    if (details.tabId <= 0) return;
    const reqs = tabRequests.get(details.tabId);
    if (reqs) {
      reqs.delete(details.requestId);
    }
  };

  chrome.webRequest.onCompleted.addListener(cleanupRequest, { urls: ['http://*/*', 'https://*/*'] });
  chrome.webRequest.onErrorOccurred.addListener(cleanupRequest, { urls: ['http://*/*', 'https://*/*'] });
}

export function getActiveRequestCount(tabId: number): number {
  const reqs = tabRequests.get(tabId);
  if (!reqs) return 0;

  const now = Date.now();
  // Clean up requests older than 3 s (long-polling)
  for (const [id, req] of reqs.entries()) {
    if (now - req.startTime > 3000) {
      reqs.delete(id);
    }
  }
  return reqs.size;
}

export async function waitForNetIdle(
  tabId: number,
  quietMs: number = 400,
  maxMs: number = 4000
): Promise<{ settled: boolean; elapsedMs: number }> {
  const startTime = Date.now();
  let quietSince = -1;

  while (Date.now() - startTime < maxMs) {
    const active = getActiveRequestCount(tabId);
    if (active === 0) {
      if (quietSince === -1) {
        quietSince = Date.now();
      } else if (Date.now() - quietSince >= quietMs) {
        return { settled: true, elapsedMs: Date.now() - startTime };
      }
    } else {
      quietSince = -1;
    }
    await new Promise((r) => setTimeout(r, 50));
  }

  return { settled: false, elapsedMs: Date.now() - startTime };
}
