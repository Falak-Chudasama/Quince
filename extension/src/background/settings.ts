import {
  DEFAULT_BRIDGE_HOST,
  DEFAULT_BRIDGE_PORT,
  DEFAULT_MAX_CHARS,
  BLOCKED_HOSTS_DEFAULT,
} from '../shared/constants.js';
import { ExtensionSettings } from '../shared/types.js';

const DEFAULT_SETTINGS: ExtensionSettings = {
  bridgePort: DEFAULT_BRIDGE_PORT,
  bridgeToken: '',
  blockedHosts: [...BLOCKED_HOSTS_DEFAULT],
  sensitiveHosts: [],
  riskGateEnabled: true,
  allowFileUrls: false,
  allowIncognito: false,
  trustedInputFallback: false,
  snapshotMaxChars: DEFAULT_MAX_CHARS,
};

export async function getSettings(): Promise<ExtensionSettings> {
  const result = await chrome.storage.local.get(DEFAULT_SETTINGS);
  return result as ExtensionSettings;
}

export async function updateSettings(partial: Partial<ExtensionSettings>): Promise<void> {
  await chrome.storage.local.set(partial);
}

// Session-scoped state (survives service worker restarts, lost on browser exit)
export interface SessionState {
  controlledTabIds: number[];
  groupId: number | null;
  paused: boolean;
  activeSessionId: string | null;
}

const DEFAULT_SESSION_STATE: SessionState = {
  controlledTabIds: [],
  groupId: null,
  paused: false,
  activeSessionId: null,
};

export async function getSessionState(): Promise<SessionState> {
  const res = await chrome.storage.session.get(DEFAULT_SESSION_STATE);
  return res as SessionState;
}

export async function updateSessionState(partial: Partial<SessionState>): Promise<void> {
  await chrome.storage.session.set(partial);
}
