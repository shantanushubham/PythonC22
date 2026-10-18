import type { UpiPayment } from "../src/models/payment.js";
import {
  DuplicateIdempotencyKeyError,
  DuplicatePaymentError,
  type PaymentRepository,
  type StoredPayment,
} from "../src/repositories/paymentRepository.js";
import type { Clock } from "../src/utils/clock.js";

/** A second implementation of the repository contract, used to prove substitutability. */
export class InMemoryPaymentRepository implements PaymentRepository {
  private readonly byId = new Map<string, StoredPayment>();
  private readonly byKey = new Map<string, StoredPayment>();

  async save(stored: StoredPayment): Promise<void> {
    const { idempotencyKey, payment } = stored;
    if (idempotencyKey !== null && this.byKey.has(idempotencyKey)) {
      throw new DuplicateIdempotencyKeyError();
    }
    if (this.byId.has(payment.transactionId)) {
      throw new DuplicatePaymentError();
    }
    this.byId.set(payment.transactionId, stored);
    if (idempotencyKey !== null) {
      this.byKey.set(idempotencyKey, stored);
    }
  }

  async findById(transactionId: string): Promise<StoredPayment | undefined> {
    return this.byId.get(transactionId);
  }

  async findByIdempotencyKey(idempotencyKey: string): Promise<StoredPayment | undefined> {
    return this.byKey.get(idempotencyKey);
  }
}

/** A clock the test moves by hand. */
export class FakeClock implements Clock {
  private current: number;

  constructor(start = "2026-10-18T12:00:00.000Z") {
    this.current = Date.parse(start);
  }

  now(): Date {
    return new Date(this.current);
  }

  advance(milliseconds: number): void {
    this.current += milliseconds;
  }
}

export function makePayment(overrides: Partial<UpiPayment> = {}): UpiPayment {
  return {
    transactionId: "txn_1",
    amount: "1500.50",
    currency: "INR",
    payer: { vpa: "jane.doe@okaxis", name: "Jane Doe" },
    payee: { vpa: "airpay@okicici", name: "AirPay Merchant" },
    rrn: "123456789012",
    description: "Order 1",
    reference: "order_1",
    outcome: { status: "SUCCESS" },
    createdAt: "2026-10-18T12:00:00.000Z",
    expiresAt: "2026-10-18T12:05:00.000Z",
    resolvesAt: "2026-10-18T12:00:03.000Z",
    ...overrides,
  };
}

export function makeStored(
  payment: Partial<UpiPayment> = {},
  options: { key?: string | null; fingerprint?: string } = {},
): StoredPayment {
  return {
    payment: makePayment(payment),
    fingerprint: options.fingerprint ?? "fp-1",
    idempotencyKey: options.key ?? null,
  };
}
