# Quince Chrome Extension (`extension/`)

Manifest V3 browser control extension for Quince.

## Features
- **Deterministic Observation & Action Engine**: Connects to the local Quince MCP bridge over WebSocket (`ws://127.0.0.1:7100/`).
- **Accessible DOM Snapshot Engine**: Extracts viewport and full-page interactive elements with stable refs.
- **Micro-Diff & Quiescence**: Detects mutations, network idle, toasts, and computes structured state changes.
- **Risk Gate**: Prevents execution of irreversible actions (send, pay, delete) without explicit user confirmation.
- **Safety Indicator**: Renders viewport boundary and kill pill inside a closed shadow root.
- **Emergency Stop**: Hotkey `Alt+Shift+Q` halts all actions and releases control.

## Building
```bash
npm install
npm run build
```
Output is bundled with `esbuild` into `dist/`.

## Loading into Chrome
1. Go to `chrome://extensions/`.
2. Enable Developer mode.
3. Click "Load unpacked" and select `extension/dist/`.
4. Configure port and token on the Options page (`quince_mcp/bridge/.bridge_token`).
