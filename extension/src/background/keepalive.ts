import { ALARM_INTERVAL_MINUTES, PING_INTERVAL_MS } from '../shared/constants.js';
import { log } from './logger.js';

let pingTimer: any = null;

export function startKeepAlive(sendPing: () => void, checkConnection: () => void): void {
  stopKeepAlive();

  pingTimer = setInterval(() => {
    sendPing();
  }, PING_INTERVAL_MS);

  // Chrome alarm as backup if service worker went idle
  chrome.alarms.create('quince_reconnect', { periodInMinutes: ALARM_INTERVAL_MINUTES });
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'quince_reconnect') {
      checkConnection();
    }
  });

  log('info', 'keepalive', 'Keepalive loop started');
}

export function stopKeepAlive(): void {
  if (pingTimer) {
    clearInterval(pingTimer);
    pingTimer = null;
  }
}
