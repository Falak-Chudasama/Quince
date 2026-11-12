import { SENSITIVE_WORDS_REGEX } from '../shared/constants.js';
import { getSettings } from './settings.js';
import { log } from './logger.js';

interface RiskEvaluation {
  level: 'low' | 'high';
  reason?: string;
  name?: string;
  host?: string;
  action?: string;
  ref?: string;
}

interface StoredToken {
  token: string;
  tabId: number;
  ref: string;
  action: string;
  expiresAt: number;
}

export async function evaluateRisk(
  tabId: number,
  ref: string,
  action: string,
  targetInfo: { name?: string; role?: string; tag?: string; host?: string; isSubmit?: boolean; hasSensitiveForm?: boolean }
): Promise<RiskEvaluation> {
  const settings = await getSettings();
  if (!settings.riskGateEnabled) {
    return { level: 'low' };
  }

  const name = (targetInfo.name || '').trim();
  const host = targetInfo.host || '';

  // 1. Sensitive words in name
  if (SENSITIVE_WORDS_REGEX.test(name)) {
    log('info', 'risk', `Triggered by keyword in target: "${name}"`);
    return {
      level: 'high',
      reason: `name_match:${name.slice(0, 30)}`,
      name,
      host,
      action,
      ref,
    };
  }

  // 2. Sensitive host list
  if (settings.sensitiveHosts.some((sh) => host.toLowerCase().includes(sh.toLowerCase().trim()))) {
    log('info', 'risk', `Triggered by sensitive host: ${host}`);
    return {
      level: 'high',
      reason: 'sensitive_host',
      name,
      host,
      action,
      ref,
    };
  }

  // 3. Submit button on form with sensitive inputs
  if (targetInfo.isSubmit && targetInfo.hasSensitiveForm) {
    log('info', 'risk', `Triggered by submit button on sensitive form`);
    return {
      level: 'high',
      reason: 'sensitive_form',
      name,
      host,
      action,
      ref,
    };
  }

  return { level: 'low' };
}

export async function createConfirmationToken(
  tabId: number,
  ref: string,
  action: string
): Promise<string> {
  const token = 'tok_' + Math.random().toString(36).substring(2) + Date.now().toString(36);
  const stored: StoredToken = {
    token,
    tabId,
    ref,
    action,
    expiresAt: Date.now() + 120_000, // 120 s
  };

  const key = `confirm_${token}`;
  await chrome.storage.session.set({ [key]: stored });
  return token;
}

export async function validateAndConsumeToken(
  token: string,
  tabId: number,
  ref: string,
  action: string
): Promise<boolean> {
  if (!token) return false;
  const key = `confirm_${token}`;
  const res = await chrome.storage.session.get(key);
  const stored: StoredToken | undefined = res[key];

  if (!stored) return false;
  // Always delete token on consumption (single-use)
  await chrome.storage.session.remove(key);

  if (Date.now() > stored.expiresAt) {
    log('warn', 'risk', 'Confirmation token expired');
    return false;
  }

  if (stored.tabId !== tabId || stored.ref !== ref || stored.action !== action) {
    log('warn', 'risk', 'Confirmation token parameter mismatch');
    return false;
  }

  return true;
}
