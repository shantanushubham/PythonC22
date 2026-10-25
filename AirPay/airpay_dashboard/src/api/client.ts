// A small fetch wrapper for the AirPay gateway.
//
// - `auth: "jwt"` (default) sends the access token and refreshes it when it has expired.
// - `auth: "apikey"` sends `X-API-Key`. The payment endpoints use this.
// - `auth: "none"` sends nothing (sign up, log in).
//
// Refresh tokens ROTATE: every refresh revokes the token that was sent. So two refreshes
// must never run at once, or the second one fails. `refreshTokens` shares one in-flight
// request between all callers.

import type { TokenPair } from "./types";

export const API_BASE = "/api/v1";

const REFRESH_KEY = "airpay.refresh";

// --- Tokens -------------------------------------------------------------------------------
// The access token lives in memory. The refresh token is kept in localStorage so a page
// reload does not log the customer out. (localStorage is readable by any script on the page,
// so keep the app free of third party scripts. An httpOnly cookie would need a gateway change.)

let accessToken: string | null = null;

function jwtExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

export const tokens = {
  hasRefresh: () => !!localStorage.getItem(REFRESH_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set(pair: Partial<TokenPair>) {
    if (pair.access) accessToken = pair.access;
    if (pair.refresh) localStorage.setItem(REFRESH_KEY, pair.refresh);
  },
  clear() {
    accessToken = null;
    localStorage.removeItem(REFRESH_KEY);
  },
};

type Listener = () => void;
const authLostListeners = new Set<Listener>();
/** Called when the session cannot be recovered (refresh token revoked or expired). */
export function onAuthLost(listener: Listener): () => void {
  authLostListeners.add(listener);
  return () => authLostListeners.delete(listener);
}

// --- Errors -------------------------------------------------------------------------------

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  status: number;
  errors: FieldError[];
  retryAfter?: number;

  constructor(status: number, message: string, errors: FieldError[] = [], retryAfter?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errors = errors;
    this.retryAfter = retryAfter;
  }

  /** First message for a field, such as "card.number". */
  field(name: string): string | undefined {
    return this.errors.find((e) => e.field === name)?.message;
  }

  /** `{ field: message }`, for forms. */
  get fieldMap(): Record<string, string> {
    const map: Record<string, string> = {};
    for (const e of this.errors) map[e.field] = map[e.field] ? `${map[e.field]} ${e.message}` : e.message;
    return map;
  }

  /** Message that includes field problems that the form has no input for. */
  describe(knownFields: string[] = []): string {
    const rest = this.errors.filter((e) => !knownFields.includes(e.field));
    if (!rest.length) return this.message;
    return rest.map((e) => (e.field === "body" || e.field === "non_field_errors" ? e.message : `${e.field}: ${e.message}`)).join(" · ");
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.describe();
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

// --- Refresh ------------------------------------------------------------------------------

let refreshing: Promise<string> | null = null;

export function refreshTokens(): Promise<string> {
  if (refreshing) return refreshing;
  const refresh = tokens.getRefresh();
  if (!refresh) return Promise.reject(new ApiError(401, "Not signed in"));

  refreshing = (async () => {
    let response: Response;
    try {
      response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
    } catch {
      // A network error says nothing about the session. Keep the tokens.
      throw new ApiError(0, "Cannot reach the AirPay gateway.");
    }
    if (!response.ok) {
      if (response.status === 401 || response.status === 400) {
        tokens.clear();
        authLostListeners.forEach((l) => l());
      }
      throw new ApiError(response.status, "Your session has expired. Please sign in again.");
    }
    const pair = (await response.json()) as TokenPair;
    tokens.set(pair);
    return pair.access;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function currentAccessToken(): Promise<string | null> {
  if (accessToken) {
    const exp = jwtExpiry(accessToken);
    if (!exp || exp - Date.now() > 20_000) return accessToken;
  }
  if (!tokens.hasRefresh()) return null;
  return refreshTokens();
}

// --- Request ------------------------------------------------------------------------------

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: "jwt" | "apikey" | "none";
  apiKey?: string;
  idempotencyKey?: string;
  signal?: AbortSignal;
}

async function parseError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  let errors: FieldError[] = [];
  try {
    const body = await response.json();
    if (typeof body?.message === "string") message = body.message;
    else if (typeof body?.detail === "string") message = body.detail;
    if (Array.isArray(body?.errors)) errors = body.errors;
  } catch {
    /* not JSON */
  }
  const retry = Number(response.headers.get("Retry-After"));
  return new ApiError(response.status, message, errors, Number.isFinite(retry) && retry > 0 ? retry : undefined);
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = "jwt", apiKey, idempotencyKey, signal } = options;

  const send = async (token: string | null) => {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    if (auth === "jwt" && token) headers.Authorization = `Bearer ${token}`;
    if (auth === "apikey" && apiKey) headers["X-API-Key"] = apiKey;
    try {
      return await fetch(`${API_BASE}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal,
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      throw new ApiError(0, "Cannot reach the AirPay gateway. Is it running on port 8000?");
    }
  };

  let token = auth === "jwt" ? await currentAccessToken() : null;
  if (auth === "jwt" && !token) {
    authLostListeners.forEach((l) => l());
    throw new ApiError(401, "Not signed in");
  }

  let response = await send(token);

  // The access token can expire between the check and the server. Refresh once and retry.
  if (response.status === 401 && auth === "jwt" && tokens.hasRefresh()) {
    token = await refreshTokens();
    response = await send(token);
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
