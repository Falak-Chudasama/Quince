export interface BridgeMessage {
  v?: number;
  t?: number;
  id?: string;
  type?: 'hello' | 'hello_ack' | 'req' | 'request' | 'res' | 'response' | 'event' | 'ping' | 'pong';
  method?: string;
  params?: Record<string, any>;
  result?: Record<string, any>;
  error?: {
    code: string;
    message: string;
    retryable?: boolean;
    data?: Record<string, any>;
  };
  event?: string;
  data?: Record<string, any>;
}

export interface TabInfo {
  tab_id: number;
  title: string;
  url: string;
  active: boolean;
  controlled: boolean;
  audible?: boolean;
  pinned?: boolean;
  window_id?: number;
}

export interface StateChange {
  effect: 'none' | 'dom_changed' | 'navigated' | 'new_tab' | 'value_set' | 'error';
  summary_line: string;
  before: { url: string; title: string; scroll?: number };
  after: { url: string; title: string; scroll?: number; generation?: number };
  navigated?: boolean;
  navigation_kind?: 'full' | 'spa' | 'hash' | null;
  new_tabs?: Array<{ tab_id: number; url: string; title: string }>;
  closed_tabs?: number[];
  target?: { ref: string; still_present: boolean; value_after?: string; checked_after?: boolean | null; focused?: boolean };
  focus?: { before?: string; after?: string; after_desc?: string };
  dom?: {
    added: Array<{ ref: string; desc: string; in_viewport?: boolean }>;
    removed: Array<{ ref: string; desc: string }>;
    changed: Array<{ ref: string; desc: string; fields?: Record<string, [any, any]> }>;
    overflow?: { added: number; removed: number; changed: number };
  };
  messages?: string[];
  validation_errors?: Array<{ ref: string; message: string }>;
  dialog?: { opened?: any; closed?: any; script_dialog?: { type: string; message: string; auto_response: string } | null };
  scroll?: { before: number; after: number; max: number; at_bottom?: boolean };
  no_visible_change?: boolean;
  wait?: { settled: boolean; reason: string; elapsed_ms: number; mutation_count?: number; requests_pending?: number; timed_out?: boolean };
  loop_warning?: string;
  refs_reset?: boolean;
}

export interface ExtensionSettings {
  bridgePort: number;
  bridgeToken: string;
  blockedHosts: string[];
  sensitiveHosts: string[];
  riskGateEnabled: boolean;
  allowFileUrls: boolean;
  allowIncognito: boolean;
  trustedInputFallback: boolean;
  snapshotMaxChars: number;
}
