/**
 * Service tests with no HTTP.
 *
 * Each service is built with plain collaborators, which is possible because they depend
 * on interfaces (Dependency Inversion).
 */

import { describe, expect, it } from "vitest";

import { buildDependencies, type BuildOptions } from "../src/container.js";
import { IdempotencyConflictError, PaymentNotFoundError, RequestValidationError } from "../src/errors.js";
import { silentLogger } from "../src/logger.js";
import { PaymentMapper } from "../src/mappers/paymentMapper.js";
import type {
  PaymentReader,
  PaymentRepository,
  StoredPayment,
} from "../src/repositories/paymentRepository.js";
import { SqlitePaymentRepository } from "../src/repositories/sqlitePaymentRepository.js";
import { PaymentQueryService } from "../src/services/paymentQueryService.js";
import type { OutcomeRule } from "../src/services/upiOutcomeService.js";
import { defaultOutcomeRules } from "../src/services/upiOutcomeService.js";
import { FakeClock, InMemoryPaymentRepository, makeStored } from "./fakes.js";
import { testSettings } from "./helpers.js";

const repositories: [string, () => PaymentRepository][] = [
  ["in-memory repository", () => new InMemoryPaymentRepository()],
  ["sqlite repository", () => new SqlitePaymentRepository(":memory:")],
];

function setup(
  repository: PaymentRepository = new InMemoryPaymentRepository(),
  options: Partial<BuildOptions> = {},
) {
  const clock = new FakeClock();
  const deps = buildDependencies({
    settings: testSettings(),
    repository,
    clock,
    logger: silentLogger,
    ...options,
  });
  return { ...deps, clock, repository };
}

const command = { amount: "1500.50", payerVpa: "jane.doe@okaxis", description: "Order 1", reference: "order_1" };

describe.each(repositories)("PaymentService on the %s", (_name, createRepository) => {
  it("creates a PENDING payment that later succeeds", async () => {
    const { payments, query, clock } = setup(createRepository());

    const { view, replayed } = await payments.create(command, undefined);

    expect(replayed).toBe(false);
    expect(view).toMatchObject({
      status: "PENDING",
      amount: "1500.50",
      payer: { vpa: "jane.doe@okaxis", name: "Jane Doe" },
      payee: { vpa: "airpay@okicici", name: "AirPay Merchant" },
    });
    expect((await query.get(view.transactionId)).status).toBe("PENDING");

    clock.advance(3000);

    expect((await query.get(view.transactionId)).status).toBe("SUCCESS");
  });

  it("replays a request with the same key, in its current state", async () => {
    const { payments, clock } = setup(createRepository());
    const first = await payments.create(command, "key-1");
    clock.advance(3000);

    const second = await payments.create(command, "key-1");

    expect(second.replayed).toBe(true);
    expect(second.view.transactionId).toBe(first.view.transactionId);
    expect(first.view.status).toBe("PENDING");
    expect(second.view.status).toBe("SUCCESS");
  });

  it("rejects the same key with a different request", async () => {
    const { payments } = setup(createRepository());
    await payments.create(command, "key-1");

    await expect(payments.create({ ...command, amount: "99.00" }, "key-1")).rejects.toBeInstanceOf(
      IdempotencyConflictError,
    );
  });

  it("never replays payments that have no key", async () => {
    const { payments } = setup(createRepository());

    const first = await payments.create(command, undefined);
    const second = await payments.create(command, undefined);

    expect(second.replayed).toBe(false);
    expect(second.view.transactionId).not.toBe(first.view.transactionId);
  });

  it("creates exactly one payment when the same request arrives many times at once", async () => {
    const { payments } = setup(createRepository());

    const results = await Promise.all(Array.from({ length: 8 }, () => payments.create(command, "race")));

    expect(new Set(results.map((result) => result.view.transactionId)).size).toBe(1);
    expect(results.filter((result) => !result.replayed)).toHaveLength(1);
  });

  it("returns one winner and conflicts when concurrent requests share a key but differ", async () => {
    const { payments } = setup(createRepository());

    const results = await Promise.allSettled(
      Array.from({ length: 6 }, (_, index) => payments.create({ ...command, reference: `order_${index}` }, "mixed")),
    );

    expect(results.filter((result) => result.status === "fulfilled")).toHaveLength(1);
    for (const result of results) {
      if (result.status === "rejected") expect(result.reason).toBeInstanceOf(IdempotencyConflictError);
    }
  });
});

describe("PaymentService validation", () => {
  it("rejects a VPA that does not exist and stores nothing", async () => {
    const { payments, repository } = setup();

    const error = await payments
      .create({ ...command, payerVpa: "ghost.notfound@okaxis" }, "key-bad")
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(RequestValidationError);
    expect((error as RequestValidationError).errors).toEqual([{ field: "payer_vpa", message: "VPA does not exist" }]);
    expect(await repository.findByIdempotencyKey("key-bad")).toBeUndefined();
  });

  it("rejects an unsupported handle", async () => {
    const { payments } = setup();

    await expect(payments.create({ ...command, payerVpa: "jane@nobank" }, undefined)).rejects.toBeInstanceOf(
      RequestValidationError,
    );
  });

  it("rejects a bad idempotency key before doing anything else", async () => {
    const { payments } = setup();

    await expect(payments.create(command, "bad key!")).rejects.toThrow("Idempotency-Key");
  });
});

describe("outcomes over time", () => {
  it("fails with the scenario's code once the payer responds", async () => {
    const { payments, query, clock } = setup();
    const { view } = await payments.create({ ...command, payerVpa: "insufficient.funds@ybl" }, undefined);

    expect((await query.get(view.transactionId)).failureCode).toBeUndefined();
    clock.advance(3000);

    expect(await query.get(view.transactionId)).toMatchObject({
      status: "FAILED",
      failureCode: "INSUFFICIENT_FUNDS",
      failureReason: "Insufficient funds",
    });
  });

  it("expires only when the collect request times out", async () => {
    const { payments, query, clock } = setup();
    const { view } = await payments.create({ ...command, payerVpa: "expired.user@paytm" }, undefined);

    clock.advance(60_000);
    expect((await query.get(view.transactionId)).status).toBe("PENDING");

    clock.advance(240_000);
    expect(await query.get(view.transactionId)).toMatchObject({ status: "EXPIRED", failureCode: "COLLECT_EXPIRED" });
  });

  it("resolves immediately when the approval delay is zero", async () => {
    const { payments } = setup(undefined, { settings: testSettings({ approvalDelayMs: 0 }) });

    const { view } = await payments.create(command, undefined);

    expect(view.status).toBe("SUCCESS");
  });

  it("applies the configured transaction limit", async () => {
    const { payments, query, clock } = setup(undefined, { settings: testSettings({ transactionLimit: "500.00" }) });
    const { view } = await payments.create({ ...command, amount: "500.01" }, undefined);
    clock.advance(3000);

    expect((await query.get(view.transactionId)).failureCode).toBe("LIMIT_EXCEEDED");
  });
});

describe("extension without editing existing code", () => {
  it("adds a decline scenario as a rule", async () => {
    const odd: OutcomeRule = {
      evaluate: (attempt) =>
        attempt.amountPaise % 2n === 1n ? { status: "FAILED", failureCode: "BANK_UNAVAILABLE", failureReason: "Odd paise" } : null,
    };
    const { payments, query, clock } = setup(undefined, {
      outcomeRules: [...defaultOutcomeRules("100000.00"), odd],
    });

    const { view } = await payments.create({ ...command, amount: "10.01" }, undefined);
    clock.advance(3000);

    expect(await query.get(view.transactionId)).toMatchObject({ status: "FAILED", failureReason: "Odd paise" });
  });

  it("adds a handle as data", async () => {
    const { payments } = setup(undefined, { handles: [{ handle: "newbank", bankName: "New Bank" }], settings: testSettings({ merchantVpa: "shop@newbank" }) });

    const { view } = await payments.create({ ...command, payerVpa: "jane@newbank" }, undefined);

    expect(view.payer.vpa).toBe("jane@newbank");
    expect(view.payee.vpa).toBe("shop@newbank");
  });

  it("refuses to start with a merchant VPA on an unsupported handle", () => {
    expect(() => setup(undefined, { settings: testSettings({ merchantVpa: "shop@nobank" }) })).toThrow("UPI_MERCHANT_VPA");
  });
});

describe("PaymentQueryService", () => {
  it("needs only a reader, so it cannot write", async () => {
    const reader: PaymentReader = {
      findById: async (id): Promise<StoredPayment | undefined> =>
        id === "txn_ro" ? makeStored({ transactionId: "txn_ro" }) : undefined,
      findByIdempotencyKey: async () => undefined,
    };
    const service = new PaymentQueryService(reader, new PaymentMapper(), new FakeClock("2026-10-18T12:10:00.000Z"));

    expect((await service.get("txn_ro")).status).toBe("SUCCESS");
    await expect(service.get("txn_unknown")).rejects.toBeInstanceOf(PaymentNotFoundError);
  });
});
