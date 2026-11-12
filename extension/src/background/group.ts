import { getSessionState, updateSessionState } from './settings.js';
import { log } from './logger.js';

export async function ensureQuinceGroup(tabId: number): Promise<number> {
  const session = await getSessionState();
  let groupId = session.groupId;

  // Check if group is still valid
  if (groupId !== null) {
    try {
      const g = await chrome.tabGroups.get(groupId);
      if (g) {
        await chrome.tabs.group({ tabIds: [tabId], groupId });
        return groupId;
      }
    } catch {
      groupId = null;
    }
  }

  // Create new group
  try {
    groupId = await chrome.tabs.group({ tabIds: [tabId] });
    await chrome.tabGroups.update(groupId, {
      title: 'Quince',
      color: 'yellow',
      collapsed: false,
    });
    await updateSessionState({ groupId });
    log('info', 'group', `Created Quince tab group id ${groupId} for tab ${tabId}`);
    return groupId;
  } catch (err: any) {
    log('warn', 'group', `Failed to create/join tab group: ${err.message}`);
    return -1;
  }
}
