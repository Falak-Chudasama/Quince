import { bridgeClient } from './bridge.js';
import { log } from './logger.js';
import { setupNetIdleTracking } from './net-idle.js';
import { abortSession } from './session.js';

log('info', 'sw', 'Quince background service worker starting up...');

setupNetIdleTracking();

// Listen for emergency stop command
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'emergency-stop') {
    log('warn', 'sw', 'Emergency stop command triggered by hotkey Alt+Shift+Q');
    await abortSession('emergency_stop');
  }
});

// React to setting changes
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && (changes.bridgePort || changes.bridgeToken)) {
    log('info', 'sw', 'Bridge settings updated; reconnecting...');
    bridgeClient.connect();
  }
});

// Handle initial connection
bridgeClient.connect();
