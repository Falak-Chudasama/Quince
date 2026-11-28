document.addEventListener('DOMContentLoaded', async () => {
  const form = document.getElementById('settings-form') as HTMLFormElement;
  const portInput = document.getElementById('bridge-port') as HTMLInputElement;
  const tokenInput = document.getElementById('bridge-token') as HTMLInputElement;
  const riskGateInput = document.getElementById('risk-gate') as HTMLInputElement;
  const blockedHostsInput = document.getElementById('blocked-hosts') as HTMLTextAreaElement;
  const sensitiveHostsInput = document.getElementById('sensitive-hosts') as HTMLTextAreaElement;
  const testBtn = document.getElementById('test-btn') as HTMLButtonElement;
  const statusMsg = document.getElementById('status-msg') as HTMLDivElement;

  const current = await chrome.storage.local.get({
    bridgePort: 7100,
    bridgeToken: '',
    riskGateEnabled: true,
    blockedHosts: ['chromewebstore.google.com'],
    sensitiveHosts: [],
  });

  portInput.value = String(current.bridgePort);
  tokenInput.value = current.bridgeToken || '';
  riskGateInput.checked = current.riskGateEnabled;
  blockedHostsInput.value = (current.blockedHosts || []).join('\n');
  sensitiveHostsInput.value = (current.sensitiveHosts || []).join('\n');

  form.onsubmit = async (e) => {
    e.preventDefault();
    const port = parseInt(portInput.value, 10) || 7100;
    const token = tokenInput.value.trim();
    const riskGate = riskGateInput.checked;
    const blocked = blockedHostsInput.value
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);
    const sensitive = sensitiveHostsInput.value
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);

    await chrome.storage.local.set({
      bridgePort: port,
      bridgeToken: token,
      riskGateEnabled: riskGate,
      blockedHosts: blocked,
      sensitiveHosts: sensitive,
    });

    statusMsg.className = 'status-msg success';
    statusMsg.textContent = 'Settings saved successfully!';
    setTimeout(() => {
      statusMsg.textContent = '';
    }, 3000);
  };

  testBtn.onclick = () => {
    statusMsg.className = 'status-msg';
    statusMsg.textContent = 'Testing connection to bridge...';

    const port = parseInt(portInput.value, 10) || 7100;
    const token = tokenInput.value.trim();
    const hosts = ['127.0.0.1', '127.0.0.5'];
    let hostIdx = 0;

    const tryHost = () => {
      const host = hosts[hostIdx];
      const url = `ws://${host}:${port}/`;
      const ws = new WebSocket(url);

      const timeout = setTimeout(() => {
        ws.close();
        if (hostIdx + 1 < hosts.length) {
          hostIdx++;
          tryHost();
          return;
        }
        statusMsg.className = 'status-msg error';
        statusMsg.textContent = 'Connection timed out. Is Quince MCP running?';
      }, 2500);

      let handshakeCompleted = false;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            v: 1,
            type: 'hello',
            client: 'quince-extension',
            version: '0.1.0',
            token: token,
            browser: 'Chrome',
            capabilities: ['snapshot', 'actions'],
          })
        );
      };

      ws.onmessage = (event) => {
        clearTimeout(timeout);
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'hello_ack') {
            handshakeCompleted = true;
            statusMsg.className = 'status-msg success';
            statusMsg.textContent = `Connection successful on ${url}! Quince bridge acknowledged handshake.`;
          } else if (msg.type === 'error' || msg.error) {
            handshakeCompleted = true;
            statusMsg.className = 'status-msg error';
            statusMsg.textContent = `Bridge rejected: ${msg.error?.message || 'Authentication error'}`;
          }
        } catch {
          handshakeCompleted = true;
          statusMsg.className = 'status-msg success';
          statusMsg.textContent = 'Connected, but received unexpected response.';
        }
        ws.close();
      };

      ws.onclose = (event) => {
        clearTimeout(timeout);
        if (handshakeCompleted) return;
        if (event.code !== 4401 && event.code !== 4426 && hostIdx + 1 < hosts.length) {
          hostIdx++;
          tryHost();
          return;
        }
        statusMsg.className = 'status-msg error';
        if (event.code === 4401) {
          statusMsg.textContent = `Unauthorized (4401): ${event.reason || 'Token mismatch'}. Check quince_mcp/bridge/.bridge_token`;
        } else if (event.code === 4426) {
          statusMsg.textContent = `Version upgrade required (4426): ${event.reason}`;
        } else {
          statusMsg.textContent = `Could not connect to ${url} (code ${event.code}: ${event.reason || 'Server not reachable'}).`;
        }
      };

      ws.onerror = () => {
        // onclose will handle fallback or error reporting
      };
    };

    tryHost();
  };
});
