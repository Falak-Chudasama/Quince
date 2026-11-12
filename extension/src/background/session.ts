import { log } from './logger.js';
import { getSessionState, updateSessionState } from './settings.js';

export async function beginSession(sessionId: string): Promise<void> {
  await updateSessionState({ activeSessionId: sessionId, paused: false });
  log('info', 'session', `Session ${sessionId} began`);
  await updateOverlayState(true);
}

export async function endSession(sessionId: string, outcome?: string): Promise<void> {
  await updateSessionState({ activeSessionId: null, paused: false });
  log('info', 'session', `Session ${sessionId} ended: ${outcome || 'done'}`);
  await updateOverlayState(false);
}

export async function abortSession(reason: string = 'user_abort'): Promise<void> {
  const session = await getSessionState();
  if (session.activeSessionId) {
    log('warn', 'session', `Session ${session.activeSessionId} aborted: ${reason}`);
    await updateSessionState({ activeSessionId: null, paused: true });
    await updateOverlayState(false);
  }
}

export async function setPaused(paused: boolean): Promise<void> {
  await updateSessionState({ paused });
  log('info', 'session', `Control paused: ${paused}`);
  await updateOverlayState(!paused);
}

async function updateOverlayState(active: boolean): Promise<void> {
  const session = await getSessionState();
  for (const tid of session.controlledTabIds) {
    chrome.tabs.sendMessage(tid, { type: 'set_indicator', active }, () => {
      // Ignore if tab is closed or unloaded
      if (chrome.runtime.lastError) {}
    });
  }
}
