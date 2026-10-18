/**
 * Models: the payment data the services and repositories pass around.
 *
 * A UPI payment is asynchronous. When it is created, the mock already knows how it will
 * end (`outcome`) and when the payer "responds" (`resolvesAt`). Until that moment the
 * payment is PENDING. The stored record never changes. The status a caller sees is worked
 * out from the clock (see `PaymentMapper.toView`).
 */

export type PaymentStatus = "PENDING" | "SUCCESS" | "FAILED" | "EXPIRED";

export type FailureCode =
  | "INSUFFICIENT_FUNDS"
  | "PAYER_DECLINED"
  | "INCORRECT_PIN"
  | "LIMIT_EXCEEDED"
  | "BANK_UNAVAILABLE"
  | "VPA_BLOCKED"
  | "COLLECT_EXPIRED";

export interface Outcome {
  status: "SUCCESS" | "FAILED" | "EXPIRED";
  failureCode?: FailureCode;
  failureReason?: string;
}

export interface Party {
  vpa: string;
  name: string;
}

/** What is stored. Timestamps are ISO strings. */
export interface UpiPayment {
  transactionId: string;
  amount: string;
  currency: "INR";
  payer: Party;
  payee: Party;
  /** 12-digit retrieval reference number, the id banks use for a UPI transaction. */
  rrn: string;
  description: string | null;
  reference: string | null;
  outcome: Outcome;
  createdAt: string;
  expiresAt: string;
  resolvesAt: string;
}

/** What a caller sees at a given moment. */
export interface PaymentView {
  transactionId: string;
  status: PaymentStatus;
  amount: string;
  currency: "INR";
  payer: Party;
  payee: Party;
  rrn: string;
  description?: string;
  reference?: string;
  failureCode?: FailureCode;
  failureReason?: string;
  createdAt: string;
  expiresAt: string;
  completedAt?: string;
  /** Set while PENDING: how many seconds until it is worth asking again. */
  retryAfterSeconds?: number;
}
