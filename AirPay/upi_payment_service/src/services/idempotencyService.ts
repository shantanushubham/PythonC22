/** Rules for the Idempotency-Key header. */

import { createHash } from "node:crypto";

import { IdempotencyConflictError, InvalidIdempotencyKeyError } from "../errors.js";
import type { StoredPayment } from "../repositories/paymentRepository.js";
import { stableStringify } from "../utils/stableStringify.js";

const KEY_PATTERN = /^[A-Za-z0-9._:-]{1,255}$/;

export class IdempotencyService {
  /** The trimmed key, or undefined when the header was not sent. */
  cleanKey(value: string | undefined): string | undefined {
    if (value === undefined) {
      return undefined;
    }
    const key = value.trim();
    if (!KEY_PATTERN.test(key)) {
      throw new InvalidIdempotencyKeyError();
    }
    return key;
  }

  /** A hash of the request, used to tell a retry from a different request. */
  fingerprint(request: Record<string, unknown>): string {
    return createHash("sha256").update(stableStringify(request)).digest("hex");
  }

  /** Throws IdempotencyConflictError if the key was used for a different request. */
  ensureSameRequest(stored: StoredPayment, fingerprint: string): void {
    if (stored.fingerprint !== fingerprint) {
      throw new IdempotencyConflictError();
    }
  }
}
