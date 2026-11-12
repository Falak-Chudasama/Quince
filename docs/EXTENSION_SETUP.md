# Quince Browser Bridge — Chrome Extension Setup Guide

This guide walks you through building, installing, and connecting the Quince Browser Bridge extension to your local Chrome browser.

---

## 1. Build the Extension
In the project root, open a terminal:
```bash
cd extension
npm install
npm run build
```
The compiled Manifest V3 extension will be ready in `extension/dist/`.

---

## 2. Load the Unpacked Extension in Chrome
1. Open Google Chrome.
2. In the URL bar, go to `chrome://extensions/`.
3. Enable **Developer mode** using the toggle switch in the top-right corner.
4. Click **Load unpacked** in the top-left corner.
5. Select the directory:
   ```
   <repo-root>/extension/dist
   ```
6. The **Quince Browser Bridge** extension will appear in your extensions list.

---

## 3. Retrieve Your Bridge Token
1. When Quince MCP runs, it generates a bridge token and saves it to:
   ```
   quince_mcp/bridge/.bridge_token
   ```
2. Open that file and copy the token string.

---

## 4. Configure Extension Options
1. Click the Quince extension icon in Chrome's extension menu (or right-click it and choose **Options**).
2. On the Options page:
   * **Bridge Port**: Ensure it is set to `7100` (or your configured port).
   * **Bridge Token**: Paste your token from step 3.
   * Click **Save Settings**.
   * Click **Test Connection** to verify that the handshake succeeds.
3. The popup will now show **Connected**.

---

## 5. First Test Run
With Quince MCP running, trigger a browser navigation or run a test:
1. When Quince controls a tab, the tab will automatically join the **Quince** tab group and display a thin yellow border with an active indicator pill.
2. Pressing **Alt+Shift+Q** or clicking **Stop** on the indicator immediately releases control.
