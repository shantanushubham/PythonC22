import { once } from "node:events";
import type { AddressInfo } from "node:net";

import { createApp, type AppDependencies } from "../src/app.js";
import type { Settings } from "../src/config.js";
import { buildDependencies, type BuildOptions } from "../src/container.js";
import { silentLogger } from "../src/logger.js";
import { SqlitePaymentRepository } from "../src/repositories/sqlitePaymentRepository.js";
import { FakeClock } from "./fakes.js";

export function testSettings(overrides: Partial<Settings> = {}): Settings {
  return {
    port: 0,
    dbPath: ":memory:",
    approvalDelayMs: 3000,
    collectExpirySeconds: 300,
    merchantVpa: "airpay@okicici",
    merchantName: "AirPay Merchant",
    transactionLimit: "100000.00",
    ...overrides,
  };
}

export function testDependencies(options: Partial<BuildOptions> = {}): AppDependencies {
  return buildDependencies({
    settings: testSettings(),
    repository: new SqlitePaymentRepository(":memory:"),
    clock: new FakeClock(),
    logger: silentLogger,
    ...options,
  });
}

export interface ApiResponse {
  status: number;
  headers: Headers;
  body: any;
}

export interface TestServer {
  baseUrl: string;
  clock: FakeClock;
  get(path: string): Promise<ApiResponse>;
  post(path: string, body: unknown, headers?: Record<string, string>): Promise<ApiResponse>;
  close(): Promise<void>;
}

/** Starts the real app on a free port, with a clock the test controls. */
export async function startTestServer(
  options: Omit<Partial<BuildOptions>, "clock"> = {},
): Promise<TestServer> {
  const clock = new FakeClock();
  const app = createApp(testDependencies({ ...options, clock }));
  const server = app.listen(0);
  await once(server, "listening");
  const baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;

  async function send(path: string, init?: RequestInit): Promise<ApiResponse> {
    const response = await fetch(`${baseUrl}${path}`, init);
    const text = await response.text();
    let body: unknown = text;
    try {
      body = JSON.parse(text);
    } catch {
      // Not JSON, for example the docs page.
    }
    return { status: response.status, headers: response.headers, body };
  }

  return {
    baseUrl,
    clock,
    get: (path) => send(path),
    post: (path, body, headers = {}) =>
      send(path, {
        method: "POST",
        headers: { "content-type": "application/json", ...headers },
        body: typeof body === "string" ? body : JSON.stringify(body),
      }),
    close: async () => {
      server.close();
      server.closeAllConnections();
      await once(server, "close");
    },
  };
}
