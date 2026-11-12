import { DEFAULT_BRIDGE_HOST, DEFAULT_BRIDGE_PORT } from '../shared/constants.js';
import { BridgeError } from '../shared/errors.js';
import { makeErrorResponse, makeHello, makePong, makeResponse } from '../shared/protocol.js';
import { BridgeMessage } from '../shared/types.js';
import { startKeepAlive, stopKeepAlive } from './keepalive.js';
import { log } from './logger.js';
import { handleRequest } from './router.js';
import { getSettings } from './settings.js';

class BridgeClient {
  private ws: WebSocket | null = null;
  private isConnected: boolean = false;
  private reconnectAttempts: number = 0;
  private reconnectTimer: any = null;

  async connect(): Promise<void> {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const settings = await getSettings();
    const port = settings.bridgePort || DEFAULT_BRIDGE_PORT;
    const url = `ws://${DEFAULT_BRIDGE_HOST}:${port}/`;

    log('info', 'bridge', `Connecting to bridge at ${url}...`);

    try {
      this.ws = new WebSocket(url);
    } catch (err: any) {
      log('warn', 'bridge', `Failed to initialize WebSocket: ${err.message}`);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = async () => {
      log('info', 'bridge', 'WebSocket open. Sending hello...');
      const s = await getSettings();
      this.send(makeHello(s.bridgeToken));
    };

    this.ws.onmessage = async (event) => {
      let msg: BridgeMessage;
      try {
        msg = JSON.parse(event.data);
      } catch {
        log('error', 'bridge', 'Received invalid JSON from bridge');
        return;
      }

      await this.handleMessage(msg);
    };

    this.ws.onclose = (event) => {
      log('warn', 'bridge', `WebSocket closed (code=${event.code}, reason=${event.reason})`);
      this.isConnected = false;
      stopKeepAlive();
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      log('error', 'bridge', 'WebSocket error encountered');
    };
  }

  private async handleMessage(msg: BridgeMessage): Promise<void> {
    if (msg.type === 'hello_ack') {
      log('info', 'bridge', 'Handshake completed with bridge');
      this.isConnected = true;
      this.reconnectAttempts = 0;
      startKeepAlive(
        () => this.send({ v: 1, type: 'ping', t: Date.now() }),
        () => this.checkLiveness()
      );
      return;
    }

    if (msg.type === 'ping') {
      this.send(makePong((msg as any).t));
      return;
    }

    if ((msg.type === 'request' || msg.type === 'req') && msg.id && msg.method) {
      try {
        const result = await handleRequest(msg.method, msg.params || {});
        this.send(makeResponse(msg.id, result));
      } catch (err: any) {
        log('warn', 'bridge', `Error handling ${msg.method}: ${err.message}`);
        if (err instanceof BridgeError) {
          this.send(makeErrorResponse(msg.id, err.code, err.message, { retryable: err.retryable, data: err.data }));
        } else {
          this.send(makeErrorResponse(msg.id, 'internal_error', err.message || 'Internal error'));
        }
      }
    }
  }

  send(msg: BridgeMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectAttempts++;
    const base = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 15000);
    const jitter = base * (0.8 + Math.random() * 0.4);

    log('info', 'bridge', `Scheduling reconnect in ${Math.round(jitter)}ms (attempt ${this.reconnectAttempts})`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, jitter);
  }

  checkLiveness(): void {
    if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connect();
    }
  }

  getStatus() {
    return {
      connected: this.isConnected,
      reconnectAttempts: this.reconnectAttempts,
    };
  }
}

export const bridgeClient = new BridgeClient();
