/**
 * Repository contract.
 *
 * The same tests run against every implementation. If a new repository passes them, the
 * services can use it without changes (Liskov Substitution).
 */

import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterAll, describe, expect, it } from "vitest";

import {
  DuplicateIdempotencyKeyError,
  DuplicatePaymentError,
  type PaymentRepository,
} from "../src/repositories/paymentRepository.js";
import { SqlitePaymentRepository } from "../src/repositories/sqlitePaymentRepository.js";
import { InMemoryPaymentRepository, makeStored } from "./fakes.js";

const tempDir = mkdtempSync(join(tmpdir(), "upi-repo-"));
afterAll(() => rmSync(tempDir, { recursive: true, force: true }));

let fileCounter = 0;

const implementations: [string, () => PaymentRepository][] = [
  ["sqlite (memory)", () => new SqlitePaymentRepository(":memory:")],
  ["sqlite (file)", () => new SqlitePaymentRepository(join(tempDir, `contract-${fileCounter++}.db`))],
  ["in-memory", () => new InMemoryPaymentRepository()],
];

describe.each(implementations)("PaymentRepository contract: %s", (_name, create) => {
  it("returns a saved payment unchanged", async () => {
    const repository = create();
    const stored = makeStored(
      { transactionId: "txn_a", outcome: { status: "FAILED", failureCode: "PAYER_DECLINED", failureReason: "No" } },
      { key: "k1", fingerprint: "fp-a" },
    );

    await repository.save(stored);

    expect(await repository.findById("txn_a")).toEqual(stored);
  });

  it("keeps null description and reference as null", async () => {
    const repository = create();
    await repository.save(makeStored({ transactionId: "txn_n", description: null, reference: null }));

    const found = await repository.findById("txn_n");

    expect(found?.payment.description).toBeNull();
    expect(found?.payment.reference).toBeNull();
  });

  it("finds a payment by its idempotency key", async () => {
    const repository = create();
    await repository.save(makeStored({ transactionId: "txn_b" }, { key: "k2" }));

    expect((await repository.findByIdempotencyKey("k2"))?.payment.transactionId).toBe("txn_b");
  });

  it("returns undefined for unknown ids and keys", async () => {
    const repository = create();

    expect(await repository.findById("txn_missing")).toBeUndefined();
    expect(await repository.findByIdempotencyKey("missing")).toBeUndefined();
  });

  it("rejects a duplicate idempotency key and does not store the second payment", async () => {
    const repository = create();
    await repository.save(makeStored({ transactionId: "txn_first" }, { key: "same" }));

    await expect(
      repository.save(makeStored({ transactionId: "txn_second" }, { key: "same" })),
    ).rejects.toBeInstanceOf(DuplicateIdempotencyKeyError);

    expect(await repository.findById("txn_second")).toBeUndefined();
    expect((await repository.findByIdempotencyKey("same"))?.payment.transactionId).toBe("txn_first");
  });

  it("rejects a duplicate transaction id", async () => {
    const repository = create();
    await repository.save(makeStored({ transactionId: "txn_dup" }));

    await expect(repository.save(makeStored({ transactionId: "txn_dup" }))).rejects.toBeInstanceOf(
      DuplicatePaymentError,
    );
  });

  it("lets payments without a key coexist", async () => {
    const repository = create();

    await repository.save(makeStored({ transactionId: "txn_x" }));
    await repository.save(makeStored({ transactionId: "txn_y" }));

    expect(await repository.findById("txn_x")).toBeDefined();
    expect(await repository.findById("txn_y")).toBeDefined();
  });

  it("lets only one of many concurrent saves with one key win", async () => {
    const repository = create();

    const results = await Promise.allSettled(
      Array.from({ length: 8 }, (_, index) =>
        repository.save(makeStored({ transactionId: `txn_race_${index}` }, { key: "race" })),
      ),
    );

    expect(results.filter((result) => result.status === "fulfilled")).toHaveLength(1);
    for (const result of results) {
      if (result.status === "rejected") {
        expect(result.reason).toBeInstanceOf(DuplicateIdempotencyKeyError);
      }
    }
  });
});

describe("SqlitePaymentRepository", () => {
  it("keeps payments after the file is reopened", async () => {
    const path = join(tempDir, "reopen.db");
    const first = new SqlitePaymentRepository(path);
    await first.save(makeStored({ transactionId: "txn_keep" }, { key: "keep" }));
    first.close();

    const second = new SqlitePaymentRepository(path);

    expect((await second.findById("txn_keep"))?.payment.transactionId).toBe("txn_keep");
    expect(await second.findByIdempotencyKey("keep")).toBeDefined();
    second.close();
  });

  it("makes two connections to one file agree on a key", async () => {
    const path = join(tempDir, "shared.db");
    const one = new SqlitePaymentRepository(path);
    const two = new SqlitePaymentRepository(path);
    await one.save(makeStored({ transactionId: "txn_one" }, { key: "shared" }));

    await expect(
      two.save(makeStored({ transactionId: "txn_two" }, { key: "shared" })),
    ).rejects.toBeInstanceOf(DuplicateIdempotencyKeyError);

    expect((await two.findByIdempotencyKey("shared"))?.payment.transactionId).toBe("txn_one");
    one.close();
    two.close();
  });
});
