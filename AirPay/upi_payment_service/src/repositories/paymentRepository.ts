/**
 * The payment repository contract.
 *
 * Services depend on these interfaces, never on a database. Any implementation must
 * follow the contract below, so one can replace another without the services noticing
 * (Liskov Substitution). `tests/paymentRepository.test.ts` runs the same checks against
 * every implementation.
 *
 * Interface Segregation: reading and writing are separate. Code that only looks payments
 * up asks for a `PaymentReader` and cannot write.
 *
 * Methods are async so a network database can replace SQLite later without touching the
 * services.
 */

import type { UpiPayment } from "../models/payment.js";

export interface StoredPayment {
  payment: UpiPayment;
  /** Hash of the request that created it, used to tell an idempotent retry from a different request. */
  fingerprint: string;
  idempotencyKey: string | null;
}

/** A payment with this transaction id is already stored. */
export class DuplicatePaymentError extends Error {
  constructor(message = "A payment with this transaction id already exists") {
    super(message);
    this.name = "DuplicatePaymentError";
  }
}

/** A payment with this idempotency key is already stored. */
export class DuplicateIdempotencyKeyError extends DuplicatePaymentError {
  constructor(message = "A payment with this idempotency key already exists") {
    super(message);
    this.name = "DuplicateIdempotencyKeyError";
  }
}

export interface PaymentReader {
  /** The payment with this id, or undefined. Never throws for an unknown id. */
  findById(transactionId: string): Promise<StoredPayment | undefined>;
  /** The payment saved under this idempotency key, or undefined. */
  findByIdempotencyKey(idempotencyKey: string): Promise<StoredPayment | undefined>;
}

export interface PaymentWriter {
  /**
   * Store a new payment.
   *
   * Rejects with DuplicateIdempotencyKeyError if the key is already used, and with
   * DuplicatePaymentError if the transaction id is. A rejected payment is not stored.
   * Payments with no idempotency key never collide with each other.
   * The check must be atomic: of several concurrent saves with one key, exactly one wins.
   */
  save(payment: StoredPayment): Promise<void>;
}

export interface PaymentRepository extends PaymentReader, PaymentWriter {}
