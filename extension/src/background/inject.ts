import { BridgeError } from '../shared/errors.js';
import { log } from './logger.js';

export async function ensureInjected(tabId: number): Promise<void> {
  // Test if content script is active by sending a ping
  const pingOk = await new Promise<boolean>((resolve) => {
    chrome.tabs.sendMessage(tabId, { type: 'ping' }, (response) => {
      if (chrome.runtime.lastError || !response || response.type !== 'pong') {
        resolve(false);
      } else {
        resolve(true);
      }
    });
  });

  if (pingOk) {
    return;
  }

  // Not active; attempt to inject content.js
  log('info', 'inject', `Injecting content script into tab ${tabId}`);
  try {
    await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      files: ['content.js'],
    });
  } catch (err: any) {
    log('error', 'inject', `Failed to inject into tab ${tabId}: ${err.message}`);
    throw new BridgeError('restricted_page', `Cannot control this page: ${err.message}`);
  }

  // Wait a short moment for content script initialization
  await new Promise((r) => setTimeout(r, 100));
}
