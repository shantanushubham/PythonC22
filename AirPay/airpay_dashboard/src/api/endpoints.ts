// One function per gateway endpoint. Paths match payment_gateway_django/*/urls.py.

import { request, tokens } from "./client";
import type {
  APIKey,
  AddBankAccountInput,
  Balance,
  BankAccount,
  CreateTransactionInput,
  CreatedAPIKey,
  Customer,
  Health,
  Payout,
  Refund,
  CreateRefundInput,
  ProfileUpdate,
  RegisterInput,
  SettleResult,
  Settlement,
  TokenPair,
  Transaction,
  UpdateBankAccountInput,
  WhoAmI,
} from "./types";

// --- Health ---
export const getHealth = (signal?: AbortSignal) => request<Health>("/health", { auth: "none", signal });

// --- Auth ---
export const register = (input: RegisterInput) =>
  request<Customer>("/customers", { method: "POST", body: input, auth: "none" });

export async function login(email: string, password: string): Promise<TokenPair> {
  const pair = await request<TokenPair>("/auth/login", { method: "POST", body: { email, password }, auth: "none" });
  tokens.set(pair);
  return pair;
}

/** Revokes the refresh token on the server, then forgets both tokens. */
export async function logout(): Promise<void> {
  const refresh = tokens.getRefresh();
  try {
    if (refresh) await request<void>("/auth/logout", { method: "POST", body: { refresh }, auth: "none" });
  } finally {
    tokens.clear();
  }
}

// --- Profile ---
export const getMe = (signal?: AbortSignal) => request<Customer>("/customers/me", { signal });
export const updateMe = (patch: ProfileUpdate) => request<Customer>("/customers/me", { method: "PATCH", body: patch });

// --- API keys (JWT) ---
export const listApiKeys = (signal?: AbortSignal) => request<APIKey[]>("/customers/me/api-keys", { signal });
export const getApiKey = (id: string) => request<APIKey>(`/customers/me/api-keys/${id}`);
export const createApiKey = (input: { name: string; expires_at: string }) =>
  request<CreatedAPIKey>("/customers/me/api-keys", { method: "POST", body: input });
export const revokeApiKey = (id: string) => request<void>(`/customers/me/api-keys/${id}`, { method: "DELETE" });

// --- Bank accounts (JWT) ---
export const listBankAccounts = (signal?: AbortSignal) =>
  request<BankAccount[]>("/customers/me/bank-accounts", { signal });
export const getBankAccount = (id: string) => request<BankAccount>(`/customers/me/bank-accounts/${id}`);
export const addBankAccount = (input: AddBankAccountInput) =>
  request<BankAccount>("/customers/me/bank-accounts", { method: "POST", body: input });
export const updateBankAccount = (id: string, patch: UpdateBankAccountInput) =>
  request<BankAccount>(`/customers/me/bank-accounts/${id}`, { method: "PATCH", body: patch });
export const removeBankAccount = (id: string) =>
  request<void>(`/customers/me/bank-accounts/${id}`, { method: "DELETE" });

// --- Transactions the customer has collected (JWT) ---
export const listMyTransactions = (signal?: AbortSignal) =>
  request<Transaction[]>("/customers/me/transactions", { signal });
/** If the transaction is still PENDING the gateway asks the rail again, and may credit the wallet. */
export const getMyTransaction = (id: string, signal?: AbortSignal) =>
  request<Transaction>(`/customers/me/transactions/${id}`, { signal });

// --- Refunds (JWT only: an API key cannot refund) ---
export const listRefunds = (signal?: AbortSignal) => request<Refund[]>("/customers/me/refunds", { signal });
export const getRefund = (id: string, signal?: AbortSignal) => request<Refund>(`/customers/me/refunds/${id}`, { signal });
export const listTransactionRefunds = (transactionId: string, signal?: AbortSignal) =>
  request<Refund[]>(`/customers/me/transactions/${transactionId}/refunds`, { signal });
export const createRefund = (transactionId: string, input: CreateRefundInput, idempotencyKey: string) =>
  request<Refund>(`/customers/me/transactions/${transactionId}/refunds`, { method: "POST", body: input, idempotencyKey });

// --- Balance, settlement, payouts (JWT) ---
export const getBalance = (signal?: AbortSignal) => request<Balance>("/customers/me/balance", { signal });
export const settle = (input: { bank_account_id: string; amount?: string }) =>
  request<SettleResult>("/customers/me/settle", { method: "POST", body: input });
export const listSettlements = (signal?: AbortSignal) =>
  request<Settlement[]>("/customers/me/settlements", { signal });
export const listPayouts = (signal?: AbortSignal) => request<Payout[]>("/customers/me/payouts", { signal });
export const getPayout = (id: string) => request<Payout>(`/customers/me/payouts/${id}`);
export const requestPayout = (input: { amount: string; bank_account_id: string }, idempotencyKey: string) =>
  request<Payout>("/customers/me/payouts", { method: "POST", body: input, idempotencyKey });

// --- Payment API (API key, not JWT) ---
export const paymentWhoAmI = (apiKey: string) => request<WhoAmI>("/payments/whoami", { auth: "apikey", apiKey });
export const createTransaction = (apiKey: string, input: CreateTransactionInput, idempotencyKey: string) =>
  request<Transaction>("/transactions", { method: "POST", body: input, auth: "apikey", apiKey, idempotencyKey });
export const listTransactionsWithKey = (apiKey: string) =>
  request<Transaction[]>("/transactions", { auth: "apikey", apiKey });
export const getTransactionWithKey = (apiKey: string, id: string, signal?: AbortSignal) =>
  request<Transaction>(`/transactions/${id}`, { auth: "apikey", apiKey, signal });
