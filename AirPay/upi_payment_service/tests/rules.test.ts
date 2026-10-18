import { describe, expect, it } from "vitest";

import { loadSettings } from "../src/config.js";
import { PaymentMapper } from "../src/mappers/paymentMapper.js";
import { IdempotencyService } from "../src/services/idempotencyService.js";
import { ResolutionPolicy } from "../src/services/resolutionPolicy.js";
import {
  AmountLimitRule,
  PayerScenarioRule,
  UpiOutcomeService,
  defaultOutcomeRules,
  type OutcomeRule,
} from "../src/services/upiOutcomeService.js";
import {
  DEFAULT_HANDLES,
  HandleRegistry,
  VpaValidationService,
  defaultVpaChecks,
  holderNameFor,
  type VpaCheck,
} from "../src/services/vpaValidationService.js";
import { canonicalAmount, formatPaise, isAmountFormat, toPaise } from "../src/utils/amount.js";
import { stableStringify } from "../src/utils/stableStringify.js";
import { maskVpa, parseVpa } from "../src/utils/vpa.js";
import { IdempotencyConflictError, InvalidIdempotencyKeyError } from "../src/errors.js";
import { makePayment, makeStored } from "./fakes.js";

function attempt(local: string, amount = "10.00") {
  const payer = parseVpa(`${local}@okaxis`);
  if (payer === null) throw new Error("bad test VPA");
  return { payer, amountPaise: toPaise(amount) };
}

describe("amounts", () => {
  it("converts between paise and strings without floats", () => {
    expect(toPaise("1500.5")).toBe(150050n);
    expect(toPaise("0.07")).toBe(7n);
    expect(toPaise("12")).toBe(1200n);
    expect(formatPaise(150050n)).toBe("1500.50");
    expect(formatPaise(7n)).toBe("0.07");
    expect(canonicalAmount("1500.5")).toBe("1500.50");
    expect(canonicalAmount("12")).toBe("12.00");
  });

  it("accepts only plain decimals with at most two places", () => {
    for (const good of ["1", "1.5", "1.50", "100000.00"]) expect(isAmountFormat(good)).toBe(true);
    for (const bad of ["", "-1", "1.505", "1e3", "abc", "1,000", ".5", "1."]) {
      expect(isAmountFormat(bad)).toBe(false);
    }
  });
});

describe("VPAs", () => {
  it("normalizes case and splits the parts", () => {
    expect(parseVpa("  Jane.Doe@OkAxis ")).toEqual({
      address: "jane.doe@okaxis",
      local: "jane.doe",
      handle: "okaxis",
    });
  });

  it("rejects malformed addresses", () => {
    for (const bad of ["", "jane", "@okaxis", "jane@", "j@okaxis", "jane doe@okaxis", "jane@ok axis", "jane@@okaxis"]) {
      expect(parseVpa(bad), bad).toBeNull();
    }
  });

  it("masks addresses for logs", () => {
    expect(maskVpa("jane.doe@okaxis")).toBe("ja***@okaxis");
  });

  it("makes up a holder name from the VPA", () => {
    expect(holderNameFor("jane.doe")).toBe("Jane Doe");
    expect(holderNameFor("ravi_kumar99")).toBe("Ravi Kumar");
    expect(holderNameFor("12345")).toBe("UPI User");
  });
});

describe("VpaValidationService", () => {
  const service = new VpaValidationService(new HandleRegistry(DEFAULT_HANDLES), defaultVpaChecks());

  it("resolves a good VPA to a name and bank", () => {
    const result = service.validate("jane.doe@okaxis");

    expect(result).toMatchObject({ valid: true, accountHolderName: "Jane Doe", bankName: "Axis Bank" });
  });

  it("explains why a VPA cannot be used", () => {
    expect(service.validate("ghost.notfound@okaxis")).toMatchObject({ valid: false, reason: "VPA does not exist" });
    expect(service.validate("jane@nobank")).toMatchObject({ valid: false, reason: "Unsupported UPI handle '@nobank'" });
    expect(service.validate("nonsense")).toMatchObject({ valid: false, reason: "VPA format is invalid" });
  });

  it("supports a new handle by adding data", () => {
    const extended = new VpaValidationService(
      new HandleRegistry([...DEFAULT_HANDLES, { handle: "newbank", bankName: "New Bank" }]),
      defaultVpaChecks(),
    );

    expect(service.validate("jane@newbank").valid).toBe(false);
    expect(extended.validate("jane@newbank")).toMatchObject({ valid: true, bankName: "New Bank" });
  });

  it("supports a new rule by adding a check", () => {
    const noTestVpas: VpaCheck = { check: (vpa) => (vpa.local.startsWith("test") ? "Test VPAs are not allowed" : null) };
    const strict = new VpaValidationService(new HandleRegistry(DEFAULT_HANDLES), [...defaultVpaChecks(), noTestVpas]);

    expect(strict.validate("test.user@okaxis")).toMatchObject({ valid: false, reason: "Test VPAs are not allowed" });
    expect(strict.validate("jane@okaxis").valid).toBe(true);
  });
});

describe("UpiOutcomeService", () => {
  const service = new UpiOutcomeService(defaultOutcomeRules("100000.00"));

  it("approves a VPA with no scenario keyword", () => {
    expect(service.decide(attempt("jane.doe"))).toEqual({ status: "SUCCESS" });
  });

  it.each([
    ["insufficient.funds", "FAILED", "INSUFFICIENT_FUNDS"],
    ["declined.user", "FAILED", "PAYER_DECLINED"],
    ["pinfail", "FAILED", "INCORRECT_PIN"],
    ["bankdown", "FAILED", "BANK_UNAVAILABLE"],
    ["blocked", "FAILED", "VPA_BLOCKED"],
    ["expired.user", "EXPIRED", "COLLECT_EXPIRED"],
  ])("maps %s to %s (%s)", (local, status, code) => {
    expect(service.decide(attempt(local))).toMatchObject({ status, failureCode: code });
  });

  it("declines amounts above the limit, and allows the limit itself", () => {
    expect(service.decide(attempt("jane", "100000.01"))).toMatchObject({ status: "FAILED", failureCode: "LIMIT_EXCEEDED" });
    expect(service.decide(attempt("jane", "100000.00")).status).toBe("SUCCESS");
  });

  it("checks rules in order", () => {
    expect(service.decide(attempt("insufficient", "200000.00")).failureCode).toBe("LIMIT_EXCEEDED");
  });

  it("supports a new scenario by adding a rule", () => {
    const luckyRule: OutcomeRule = {
      evaluate: (a) => (a.amountPaise === 77700n ? { status: "FAILED", failureCode: "BANK_UNAVAILABLE", failureReason: "Unlucky" } : null),
    };
    const extended = new UpiOutcomeService([...defaultOutcomeRules("100000.00"), luckyRule]);

    expect(extended.decide(attempt("jane", "777.00")).failureReason).toBe("Unlucky");
    expect(service.decide(attempt("jane", "777.00")).status).toBe("SUCCESS");
  });

  it("returns a fresh outcome each time, so callers cannot change the rule", () => {
    const rule = new PayerScenarioRule();

    const first = rule.evaluate(attempt("declined"));
    if (first !== null) first.failureReason = "changed";

    expect(rule.evaluate(attempt("declined"))?.failureReason).toBe("Payer declined the collect request");
  });

  it("has a limit rule that can be used alone", () => {
    expect(new AmountLimitRule("5.00").evaluate(attempt("jane", "5.01"))).not.toBeNull();
    expect(new AmountLimitRule("5.00").evaluate(attempt("jane", "5.00"))).toBeNull();
  });
});

describe("ResolutionPolicy", () => {
  const created = new Date("2026-10-18T12:00:00.000Z");
  const expires = new Date("2026-10-18T12:05:00.000Z");

  it("resolves approvals and failures after the approval delay", () => {
    const policy = new ResolutionPolicy(3000);

    expect(policy.resolvesAt({ status: "SUCCESS" }, created, expires).toISOString()).toBe("2026-10-18T12:00:03.000Z");
    expect(policy.resolvesAt({ status: "FAILED" }, created, expires).toISOString()).toBe("2026-10-18T12:00:03.000Z");
  });

  it("resolves an expiry only when the request times out", () => {
    expect(new ResolutionPolicy(3000).resolvesAt({ status: "EXPIRED" }, created, expires)).toEqual(expires);
  });

  it("never resolves after the request has expired", () => {
    expect(new ResolutionPolicy(10 * 60_000).resolvesAt({ status: "SUCCESS" }, created, expires)).toEqual(expires);
  });
});

describe("PaymentMapper.toView", () => {
  const mapper = new PaymentMapper();
  const payment = makePayment({
    outcome: { status: "FAILED", failureCode: "INSUFFICIENT_FUNDS", failureReason: "Insufficient funds" },
  });

  it("is PENDING before the payer responds, with a retry hint", () => {
    const view = mapper.toView(payment, new Date("2026-10-18T12:00:01.000Z"));

    expect(view.status).toBe("PENDING");
    expect(view.retryAfterSeconds).toBe(2);
    expect(view.completedAt).toBeUndefined();
    expect(view.failureCode).toBeUndefined();
  });

  it("hides the failure until it has happened", () => {
    expect(mapper.toView(payment, new Date("2026-10-18T12:00:02.999Z")).failureReason).toBeUndefined();
  });

  it("shows the final outcome from the moment it resolves", () => {
    const view = mapper.toView(payment, new Date("2026-10-18T12:00:03.000Z"));

    expect(view).toMatchObject({
      status: "FAILED",
      failureCode: "INSUFFICIENT_FUNDS",
      completedAt: "2026-10-18T12:00:03.000Z",
    });
    expect(view.retryAfterSeconds).toBeUndefined();
  });

  it("never asks the caller to retry in under a second", () => {
    expect(mapper.toView(payment, new Date("2026-10-18T12:00:02.900Z")).retryAfterSeconds).toBe(1);
  });

  it("builds a payment with a txn id and a 12-digit RRN", () => {
    const built = mapper.toPayment({
      amount: "10.00",
      payer: payment.payer,
      payee: payment.payee,
      outcome: { status: "SUCCESS" },
      createdAt: new Date("2026-10-18T12:00:00.000Z"),
      expiresAt: new Date("2026-10-18T12:05:00.000Z"),
      resolvesAt: new Date("2026-10-18T12:00:03.000Z"),
    });

    expect(built.transactionId).toMatch(/^txn_[0-9a-f-]{36}$/);
    expect(built.rrn).toMatch(/^\d{12}$/);
    expect(built.description).toBeNull();
  });
});

describe("IdempotencyService", () => {
  const service = new IdempotencyService();

  it("trims keys and allows no key", () => {
    expect(service.cleanKey("  order-1 ")).toBe("order-1");
    expect(service.cleanKey(undefined)).toBeUndefined();
  });

  it.each(["", "   ", "has space", "semi;colon", "x".repeat(256)])("rejects the key %j", (bad) => {
    expect(() => service.cleanKey(bad)).toThrow(InvalidIdempotencyKeyError);
  });

  it("fingerprints equal requests equally, whatever the key order", () => {
    expect(service.fingerprint({ a: 1, b: 2 })).toBe(service.fingerprint({ b: 2, a: 1 }));
    expect(service.fingerprint({ a: 1 })).not.toBe(service.fingerprint({ a: 2 }));
  });

  it("ignores undefined fields", () => {
    expect(service.fingerprint({ a: 1, b: undefined })).toBe(service.fingerprint({ a: 1 }));
  });

  it("raises a conflict only when the fingerprints differ", () => {
    const stored = makeStored({}, { fingerprint: "same" });

    expect(() => service.ensureSameRequest(stored, "same")).not.toThrow();
    expect(() => service.ensureSameRequest(stored, "other")).toThrow(IdempotencyConflictError);
  });
});

describe("stableStringify", () => {
  it("sorts keys at every depth", () => {
    expect(stableStringify({ b: { d: 1, c: 2 }, a: [3, { z: 1, y: 2 }] })).toBe(
      '{"a":[3,{"y":2,"z":1}],"b":{"c":2,"d":1}}',
    );
  });
});

describe("settings", () => {
  it("has working defaults", () => {
    expect(loadSettings({})).toMatchObject({
      port: 8003,
      approvalDelayMs: 3000,
      collectExpirySeconds: 300,
      merchantVpa: "airpay@okicici",
      transactionLimit: "100000.00",
    });
  });

  it("reads overrides from the environment", () => {
    const settings = loadSettings({ PORT: "9000", UPI_APPROVAL_DELAY_MS: "0", UPI_TRANSACTION_LIMIT: "5000.00" });

    expect(settings).toMatchObject({ port: 9000, approvalDelayMs: 0, transactionLimit: "5000.00" });
  });

  it.each([
    [{ PORT: "abc" }, "PORT"],
    [{ PORT: "70000" }, "PORT"],
    [{ UPI_APPROVAL_DELAY_MS: "-1" }, "UPI_APPROVAL_DELAY_MS"],
    [{ UPI_TRANSACTION_LIMIT: "lots" }, "UPI_TRANSACTION_LIMIT"],
    [{ UPI_APPROVAL_DELAY_MS: "999999", UPI_COLLECT_EXPIRY_SECONDS: "10" }, "longer than the collect expiry"],
  ])("rejects bad settings %j", (env, mention) => {
    expect(() => loadSettings(env)).toThrow(mention);
  });
});
