async function initPopup() {
  const statusPill = document.getElementById('status-pill')!;
  const bridgeUrl = document.getElementById('bridge-url')!;
  const sessionInfo = document.getElementById('session-info')!;
  const pauseBtn = document.getElementById('pause-btn')!;
  const optionsBtn = document.getElementById('options-btn')!;
  const tabsList = document.getElementById('tabs-list')!;

  const settings = await chrome.storage.local.get({ bridgePort: 7100 });
  bridgeUrl.textContent = `ws://127.0.0.1:${settings.bridgePort}/`;

  const session = await chrome.storage.session.get({
    activeSessionId: null,
    paused: false,
    controlledTabIds: [],
  });

  if (session.activeSessionId) {
    sessionInfo.textContent = session.activeSessionId.slice(0, 8) + '...';
  } else {
    sessionInfo.textContent = 'None';
  }

  if (session.paused) {
    pauseBtn.textContent = 'Resume Quince';
    (pauseBtn as HTMLElement).style.background = '#22c55e';
    (pauseBtn as HTMLElement).style.color = '#fff';
  } else {
    pauseBtn.textContent = 'Pause Quince';
  }

  pauseBtn.onclick = async () => {
    const isPaused = session.paused;
    await chrome.storage.session.set({ paused: !isPaused });
    window.close();
  };

  optionsBtn.onclick = () => {
    chrome.runtime.openOptionsPage();
  };

  if (session.controlledTabIds && session.controlledTabIds.length > 0) {
    tabsList.innerHTML = '';
    for (const tid of session.controlledTabIds) {
      const tab = await chrome.tabs.get(tid).catch(() => null);
      const row = document.createElement('div');
      row.style.display = 'flex';
      row.style.justifyContent = 'space-between';
      row.style.padding = '4px 0';
      row.style.fontSize = '12px';

      const title = document.createElement('span');
      title.textContent = tab?.title ? tab.title.slice(0, 25) : `Tab ${tid}`;
      title.style.overflow = 'hidden';
      title.style.textOverflow = 'ellipsis';
      title.style.whiteSpace = 'nowrap';

      const releaseBtn = document.createElement('button');
      releaseBtn.textContent = 'Release';
      releaseBtn.style.padding = '2px 6px';
      releaseBtn.style.fontSize = '10px';
      releaseBtn.style.background = '#333';
      releaseBtn.style.color = '#ccc';
      releaseBtn.style.border = 'none';
      releaseBtn.style.borderRadius = '3px';
      releaseBtn.style.cursor = 'pointer';

      releaseBtn.onclick = async () => {
        const remaining = session.controlledTabIds.filter((id: number) => id !== tid);
        await chrome.storage.session.set({ controlledTabIds: remaining });
        try {
          await chrome.tabs.ungroup(tid);
        } catch {}
        row.remove();
      };

      row.appendChild(title);
      row.appendChild(releaseBtn);
      tabsList.appendChild(row);
    }
  }
}

document.addEventListener('DOMContentLoaded', initPopup);
