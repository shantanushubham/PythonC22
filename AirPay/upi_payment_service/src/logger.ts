export interface Logger {
  info(event: string, fields?: Record<string, unknown>): void;
  error(event: string, fields?: Record<string, unknown>): void;
}

function format(level: string, event: string, fields?: Record<string, unknown>): string {
  const pairs = Object.entries(fields ?? {}).map(([key, value]) => `${key}=${String(value)}`);
  return [new Date().toISOString(), level, event, ...pairs].join(" ");
}

export const consoleLogger: Logger = {
  info: (event, fields) => console.log(format("INFO", event, fields)),
  error: (event, fields) => console.error(format("ERROR", event, fields)),
};

export const silentLogger: Logger = {
  info: () => undefined,
  error: () => undefined,
};
