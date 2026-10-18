/**
 * SQLite implementation of the payment repository, using Node's built-in `node:sqlite`.
 *
 * Payments are saved to a file, so they survive restarts. The unique index on
 * `idempotency_key` is what makes the "one payment per key" rule atomic, even across
 * several processes sharing the file.
 */

import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";
import type { StatementSync } from "node:sqlite";

import type { UpiPayment } from "../models/payment.js";
import {
  DuplicateIdempotencyKeyError,
  DuplicatePaymentError,
  type PaymentRepository,
  type StoredPayment,
} from "./paymentRepository.js";

const SCHEMA = `
CREATE TABLE IF NOT EXISTS payments (
  transaction_id  TEXT PRIMARY KEY,
  idempotency_key TEXT UNIQUE,
  fingerprint     TEXT NOT NULL,
  record          TEXT NOT NULL,
  created_at      TEXT NOT NULL
)`;

interface PaymentRow {
  record: string;
  fingerprint: string;
  idempotency_key: string | null;
}

export class SqlitePaymentRepository implements PaymentRepository {
  private readonly db: DatabaseSync;
  private readonly insert: StatementSync;
  private readonly selectById: StatementSync;
  private readonly selectByKey: StatementSync;

  constructor(path: string) {
    if (path !== ":memory:") {
      mkdirSync(dirname(path), { recursive: true });
    }
    this.db = new DatabaseSync(path);
    // WAL lets readers and a writer work at the same time. busy_timeout makes a writer
    // wait for the lock instead of failing at once.
    this.db.exec("PRAGMA journal_mode = WAL");
    this.db.exec("PRAGMA busy_timeout = 10000");
    this.db.exec(SCHEMA);

    this.insert = this.db.prepare(
      "INSERT INTO payments (transaction_id, idempotency_key, fingerprint, record, created_at) " +
        "VALUES (?, ?, ?, ?, ?)",
    );
    this.selectById = this.db.prepare(
      "SELECT record, fingerprint, idempotency_key FROM payments WHERE transaction_id = ?",
    );
    this.selectByKey = this.db.prepare(
      "SELECT record, fingerprint, idempotency_key FROM payments WHERE idempotency_key = ?",
    );
  }

  async save(stored: StoredPayment): Promise<void> {
    const { payment, fingerprint, idempotencyKey } = stored;
    try {
      this.insert.run(
        payment.transactionId,
        idempotencyKey,
        fingerprint,
        JSON.stringify(payment),
        payment.createdAt,
      );
    } catch (error) {
      if (isUniqueViolation(error, "idempotency_key")) {
        throw new DuplicateIdempotencyKeyError();
      }
      if (isUniqueViolation(error, "transaction_id")) {
        throw new DuplicatePaymentError();
      }
      throw error;
    }
  }

  async findById(transactionId: string): Promise<StoredPayment | undefined> {
    return toStored(this.selectById.get(transactionId) as PaymentRow | undefined);
  }

  async findByIdempotencyKey(idempotencyKey: string): Promise<StoredPayment | undefined> {
    return toStored(this.selectByKey.get(idempotencyKey) as PaymentRow | undefined);
  }

  close(): void {
    this.db.close();
  }
}

function toStored(row: PaymentRow | undefined): StoredPayment | undefined {
  if (row === undefined) {
    return undefined;
  }
  return {
    payment: JSON.parse(row.record) as UpiPayment,
    fingerprint: row.fingerprint,
    idempotencyKey: row.idempotency_key,
  };
}

function isUniqueViolation(error: unknown, column: string): boolean {
  return (
    error instanceof Error &&
    error.message.includes("UNIQUE constraint failed") &&
    error.message.includes(`payments.${column}`)
  );
}
