export interface LogEntry {
  ts: number;
  level: 'info' | 'warn' | 'error' | 'debug';
  scope: string;
  msg: string;
  data?: Record<string, any>;
}

const MAX_LOGS = 200;
const ringBuffer: LogEntry[] = [];

export function log(level: LogEntry['level'], scope: string, msg: string, data?: Record<string, any>) {
  const entry: LogEntry = {
    ts: Date.now(),
    level,
    scope,
    msg,
    data,
  };

  if (ringBuffer.length >= MAX_LOGS) {
    ringBuffer.shift();
  }
  ringBuffer.push(entry);

  const prefix = `[Quince:${scope}]`;
  if (level === 'error') {
    console.error(prefix, msg, data ?? '');
  } else if (level === 'warn') {
    console.warn(prefix, msg, data ?? '');
  } else {
    console.log(prefix, msg, data ?? '');
  }
}

export function getLogs(): LogEntry[] {
  return [...ringBuffer];
}

export function clearLogs(): void {
  ringBuffer.length = 0;
}
