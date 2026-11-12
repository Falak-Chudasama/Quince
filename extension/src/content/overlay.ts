let overlayHost: HTMLElement | null = null;

export function setOverlayActive(active: boolean): void {
  if (active) {
    showOverlay();
  } else {
    removeOverlay();
  }
}

function showOverlay(): void {
  if (overlayHost) return;

  overlayHost = document.createElement('div');
  overlayHost.setAttribute('data-quince-overlay', 'true');
  overlayHost.style.position = 'fixed';
  overlayHost.style.inset = '0';
  overlayHost.style.pointerEvents = 'none';
  overlayHost.style.zIndex = '2147483647';

  // Use closed shadow root
  const shadow = overlayHost.attachShadow({ mode: 'closed' });

  const style = document.createElement('style');
  style.textContent = `
    .quince-frame {
      position: absolute;
      inset: 0;
      border: 3px solid #f5b400;
      box-sizing: border-box;
      pointer-events: none;
    }
    .quince-pill {
      position: absolute;
      bottom: 16px;
      right: 16px;
      background: #1e1e1e;
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 13px;
      font-weight: 500;
      padding: 8px 14px;
      border-radius: 20px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
      border: 1px solid #333;
      display: flex;
      align-items: center;
      gap: 10px;
      pointer-events: auto;
    }
    .quince-dot {
      width: 8px;
      height: 8px;
      background: #f5b400;
      border-radius: 50%;
      animation: pulse 1.5s infinite;
    }
    .quince-stop {
      background: #dc3545;
      color: #fff;
      border: none;
      padding: 3px 8px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 11px;
      font-weight: 600;
    }
    .quince-stop:hover {
      background: #c82333;
    }
    @keyframes pulse {
      0% { opacity: 1; }
      50% { opacity: 0.4; }
      100% { opacity: 1; }
    }
  `;

  const container = document.createElement('div');
  container.className = 'quince-frame';

  const pill = document.createElement('div');
  pill.className = 'quince-pill';

  const dot = document.createElement('div');
  dot.className = 'quince-dot';

  const text = document.createElement('span');
  text.textContent = 'Quince is working';

  const stopBtn = document.createElement('button');
  stopBtn.className = 'quince-stop';
  stopBtn.textContent = 'Stop';
  stopBtn.onclick = () => {
    chrome.runtime.sendMessage({ type: 'abort' });
  };

  pill.appendChild(dot);
  pill.appendChild(text);
  pill.appendChild(stopBtn);
  container.appendChild(pill);

  shadow.appendChild(style);
  shadow.appendChild(container);

  (document.body || document.documentElement).appendChild(overlayHost);
}

function removeOverlay(): void {
  if (overlayHost) {
    overlayHost.remove();
    overlayHost = null;
  }
}
