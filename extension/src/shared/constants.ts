export const PROTOCOL_VERSION = 1;
export const DEFAULT_BRIDGE_PORT = 7100;
export const DEFAULT_BRIDGE_HOST = '127.0.0.1';
export const PING_INTERVAL_MS = 20000;
export const ALARM_INTERVAL_MINUTES = 0.5;

export const DEFAULT_MAX_CHARS = 6000;
export const DEFAULT_QUIET_MS = 300;
export const DEFAULT_MAX_MS = 4000;

export const MAX_FRAME_BYTES = 2 * 1024 * 1024; // 2 MB

export const BLOCKED_SCHEMES = [
  'chrome:',
  'chrome-extension:',
  'edge:',
  'about:',
  'view-source:',
  'javascript:',
  'data:',
];

export const BLOCKED_HOSTS_DEFAULT = [
  'chromewebstore.google.com',
  'chrome.google.com',
];

export const SENSITIVE_WORDS_REGEX = /\b(send|submit|pay|pay now|place order|purchase|buy|buy now|confirm|confirm order|delete|remove|erase|unsubscribe|post|publish|share|transfer|withdraw|sign out|log out|logout|authorize|allow|grant|accept|agree|apply|checkout|donate|book|reserve|subscribe|deactivate|close account|submit application)\b/i;
