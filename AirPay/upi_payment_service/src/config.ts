import { fileURLToPath } from "node:url";
import { z } from "zod";

import { formatPaise, isAmountFormat } from "./utils/amount.js";

const DEFAULT_DB_PATH = fileURLToPath(new URL("../upi_payments.db", import.meta.url));

const envSchema = z.object({
  PORT: z.coerce.number().int().min(1).max(65535).default(8003),
  UPI_PAYMENT_DB: z.string().min(1).default(DEFAULT_DB_PATH),
  // How long the payer "takes" to approve. 0 makes payments resolve immediately.
  UPI_APPROVAL_DELAY_MS: z.coerce.number().int().min(0).default(3000),
  // How long a collect request stays open before it expires.
  UPI_COLLECT_EXPIRY_SECONDS: z.coerce.number().int().min(1).default(300),
  UPI_MERCHANT_VPA: z.string().min(3).default("airpay@okicici"),
  UPI_MERCHANT_NAME: z.string().min(1).default("AirPay Merchant"),
  // Payments above this amount are declined by the mock bank (UPI's usual limit is Rs 1 lakh).
  UPI_TRANSACTION_LIMIT: z
    .string()
    .refine(isAmountFormat, "must be an amount such as 100000.00")
    .default(formatPaise(10_000_000n)),
});

export interface Settings {
  port: number;
  dbPath: string;
  approvalDelayMs: number;
  collectExpirySeconds: number;
  merchantVpa: string;
  merchantName: string;
  transactionLimit: string;
}

export function loadSettings(env: NodeJS.ProcessEnv = process.env): Settings {
  const parsed = envSchema.safeParse(env);
  if (!parsed.success) {
    const problems = parsed.error.issues
      .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
      .join("; ");
    throw new Error(`Invalid configuration: ${problems}`);
  }
  const values = parsed.data;
  if (values.UPI_APPROVAL_DELAY_MS > values.UPI_COLLECT_EXPIRY_SECONDS * 1000) {
    throw new Error("Invalid configuration: UPI_APPROVAL_DELAY_MS is longer than the collect expiry");
  }
  return {
    port: values.PORT,
    dbPath: values.UPI_PAYMENT_DB,
    approvalDelayMs: values.UPI_APPROVAL_DELAY_MS,
    collectExpirySeconds: values.UPI_COLLECT_EXPIRY_SECONDS,
    merchantVpa: values.UPI_MERCHANT_VPA,
    merchantName: values.UPI_MERCHANT_NAME,
    transactionLimit: values.UPI_TRANSACTION_LIMIT,
  };
}
