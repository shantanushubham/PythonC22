/** End-to-end tests of the HTTP API, run against the real app with a controllable clock. */

import { readFileSync } from "node:fs";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { buildOpenApiDocument } from "../src/contracts/openapiDocument.js";
import { routes, toExpressPath } from "../src/contracts/routes.js";
import { SPEC_PATH, renderSpec } from "../scripts/exportOpenapi.js";
import { startTestServer, type TestServer } from "./helpers.js";

let api: TestServer;

beforeEach(async () => {
  api = await startTestServer();
});

afterEach(async () => {
  await api.close();
});

const validBody = {
  amount: "1500.50",
  payer_vpa: "jane.doe@okaxis",
  description: "Order 1",
  reference: "order_1",
};

describe("POST /api/v1/payments", () => {
  it("starts a collect request that the payer has not answered yet", async () => {
    const response = await api.post("/api/v1/payments", validBody);

    expect(response.status).toBe(201);
    expect(response.body.success).toBe(true);
    expect(response.body.data).toMatchObject({
      status: "PENDING",
      amount: "1500.50",
      currency: "INR",
      payer: { vpa: "jane.doe@okaxis", name: "Jane Doe" },
      payee: { vpa: "airpay@okicici", name: "AirPay Merchant" },
      description: "Order 1",
      reference: "order_1",
    });
    expect(response.body.data.transaction_id).toMatch(/^txn_/);
    expect(response.body.data.rrn).toMatch(/^\d{12}$/);
    expect(response.body.data.completed_at).toBeUndefined();
    expect(response.headers.get("location")).toBe(`/api/v1/payments/${response.body.data.transaction_id}`);
  });

  it("accepts a number for the amount and keeps two decimal places", async () => {
    const response = await api.post("/api/v1/payments", { ...validBody, amount: 12.5 });

    expect(response.status).toBe(201);
    expect(response.body.data.amount).toBe("12.50");
  });

  it("normalizes the VPA to lower case", async () => {
    const response = await api.post("/api/v1/payments", { ...validBody, payer_vpa: "Jane.Doe@OkAxis" });

    expect(response.body.data.payer.vpa).toBe("jane.doe@okaxis");
  });

  it("does not return fields that are not set", async () => {
    const response = await api.post("/api/v1/payments", { amount: "10.00", payer_vpa: "jane@ybl" });

    expect(response.status).toBe(201);
    expect(response.body.data).not.toHaveProperty("description");
    expect(response.body.data).not.toHaveProperty("failure_code");
  });

  describe("validation", () => {
    it.each([
      ["a missing amount", { payer_vpa: "jane@ybl" }, "amount"],
      ["a zero amount", { amount: "0.00", payer_vpa: "jane@ybl" }, "amount"],
      ["a negative amount", { amount: "-5", payer_vpa: "jane@ybl" }, "amount"],
      ["too many decimals", { amount: "1.005", payer_vpa: "jane@ybl" }, "amount"],
      ["a non-numeric amount", { amount: "ten", payer_vpa: "jane@ybl" }, "amount"],
      ["a missing payer", { amount: "10.00" }, "payer_vpa"],
      ["a malformed payer", { amount: "10.00", payer_vpa: "nonsense" }, "payer_vpa"],
      ["another currency", { amount: "10.00", payer_vpa: "jane@ybl", currency: "USD" }, "currency"],
      ["an unknown field", { amount: "10.00", payer_vpa: "jane@ybl", surprise: 1 }, "surprise"],
    ])("rejects %s with 400", async (_name, body, field) => {
      const response = await api.post("/api/v1/payments", body);

      expect(response.status).toBe(400);
      expect(response.body.success).toBe(false);
      expect(response.body.errors.map((error: { field: string }) => error.field)).toContain(field);
    });

    it("rejects an unknown VPA with a field error", async () => {
      const response = await api.post("/api/v1/payments", { ...validBody, payer_vpa: "ghost.notfound@okaxis" });

      expect(response.status).toBe(400);
      expect(response.body.errors).toEqual([{ field: "payer_vpa", message: "VPA does not exist" }]);
    });

    it("rejects an unsupported handle", async () => {
      const response = await api.post("/api/v1/payments", { ...validBody, payer_vpa: "jane@nobank" });

      expect(response.status).toBe(400);
      expect(response.body.errors[0].message).toContain("@nobank");
    });

    it("rejects malformed JSON", async () => {
      const response = await api.post("/api/v1/payments", "{not json");

      expect(response.status).toBe(400);
      expect(response.body).toEqual({ success: false, message: "Request body is not valid JSON" });
    });

    it("rejects a body that is not an object", async () => {
      const response = await api.post("/api/v1/payments", "[1,2]");

      expect(response.status).toBe(400);
      expect(response.body.success).toBe(false);
    });

    it("rejects a bad idempotency key", async () => {
      const response = await api.post("/api/v1/payments", validBody, { "Idempotency-Key": "bad key" });

      expect(response.status).toBe(400);
      expect(response.body.message).toContain("Idempotency-Key");
    });
  });

  describe("idempotency", () => {
    it("replays the same request with the same key", async () => {
      const first = await api.post("/api/v1/payments", validBody, { "Idempotency-Key": "k1" });
      const second = await api.post("/api/v1/payments", validBody, { "Idempotency-Key": "k1" });

      expect(first.headers.get("idempotent-replayed")).toBeNull();
      expect(second.status).toBe(201);
      expect(second.headers.get("idempotent-replayed")).toBe("true");
      expect(second.body.data.transaction_id).toBe(first.body.data.transaction_id);
    });

    it("treats an equivalent body as the same request", async () => {
      const first = await api.post("/api/v1/payments", { amount: "10", payer_vpa: "Jane@YBL" }, { "Idempotency-Key": "k2" });
      const second = await api.post("/api/v1/payments", { payer_vpa: "jane@ybl", amount: 10 }, { "Idempotency-Key": "k2" });

      expect(second.headers.get("idempotent-replayed")).toBe("true");
      expect(second.body.data.transaction_id).toBe(first.body.data.transaction_id);
    });

    it("returns 409 for the same key with a different request", async () => {
      await api.post("/api/v1/payments", validBody, { "Idempotency-Key": "k3" });

      const response = await api.post("/api/v1/payments", { ...validBody, amount: "1.00" }, { "Idempotency-Key": "k3" });

      expect(response.status).toBe(409);
      expect(response.body.success).toBe(false);
    });

    it("creates separate payments without a key", async () => {
      const first = await api.post("/api/v1/payments", validBody);
      const second = await api.post("/api/v1/payments", validBody);

      expect(second.body.data.transaction_id).not.toBe(first.body.data.transaction_id);
    });

    it("shows the current state when a finished payment is replayed", async () => {
      await api.post("/api/v1/payments", validBody, { "Idempotency-Key": "k4" });
      api.clock.advance(3000);

      const replay = await api.post("/api/v1/payments", validBody, { "Idempotency-Key": "k4" });

      expect(replay.body.data.status).toBe("SUCCESS");
    });
  });
});

describe("GET /api/v1/payments/{transaction_id}", () => {
  async function create(body: object) {
    const response = await api.post("/api/v1/payments", body);
    return response.body.data.transaction_id as string;
  }

  it("is PENDING, with Retry-After, until the payer responds", async () => {
    const id = await create(validBody);
    api.clock.advance(1000);

    const response = await api.get(`/api/v1/payments/${id}`);

    expect(response.status).toBe(200);
    expect(response.body.data.status).toBe("PENDING");
    expect(response.headers.get("retry-after")).toBe("2");
  });

  it("is SUCCESS after the approval delay", async () => {
    const id = await create(validBody);
    api.clock.advance(3000);

    const response = await api.get(`/api/v1/payments/${id}`);

    expect(response.body.data.status).toBe("SUCCESS");
    expect(response.body.data.completed_at).toBe("2026-10-18T12:00:03.000Z");
    expect(response.headers.get("retry-after")).toBeNull();
  });

  it.each([
    ["insufficient.funds@okaxis", "INSUFFICIENT_FUNDS"],
    ["declined.user@oksbi", "PAYER_DECLINED"],
    ["pinfail@ybl", "INCORRECT_PIN"],
    ["bankdown@ibl", "BANK_UNAVAILABLE"],
    ["blocked@paytm", "VPA_BLOCKED"],
  ])("fails for %s with %s", async (payer_vpa, code) => {
    const id = await create({ ...validBody, payer_vpa });
    api.clock.advance(3000);

    const response = await api.get(`/api/v1/payments/${id}`);

    expect(response.body.data).toMatchObject({ status: "FAILED", failure_code: code });
    expect(response.body.data.failure_reason).toEqual(expect.any(String));
  });

  it("declines amounts above the limit", async () => {
    const id = await create({ ...validBody, amount: "100000.01" });
    api.clock.advance(3000);

    expect((await api.get(`/api/v1/payments/${id}`)).body.data.failure_code).toBe("LIMIT_EXCEEDED");
  });

  it("expires only after the collect request times out", async () => {
    const id = await create({ ...validBody, payer_vpa: "expired.user@okaxis" });

    api.clock.advance(299_000);
    expect((await api.get(`/api/v1/payments/${id}`)).body.data.status).toBe("PENDING");

    api.clock.advance(1000);
    expect((await api.get(`/api/v1/payments/${id}`)).body.data).toMatchObject({
      status: "EXPIRED",
      failure_code: "COLLECT_EXPIRED",
    });
  });

  it("gives the same answer when asked again", async () => {
    const id = await create(validBody);
    api.clock.advance(10_000);

    const first = await api.get(`/api/v1/payments/${id}`);
    const second = await api.get(`/api/v1/payments/${id}`);

    expect(second.body).toEqual(first.body);
  });

  it("returns 404 for an unknown transaction", async () => {
    const response = await api.get("/api/v1/payments/txn_missing");

    expect(response.status).toBe(404);
    expect(response.body).toMatchObject({ success: false });
  });
});

describe("POST /api/v1/vpa-validations", () => {
  it("resolves a valid VPA", async () => {
    const response = await api.post("/api/v1/vpa-validations", { vpa: "jane.doe@okhdfcbank" });

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      success: true,
      data: { vpa: "jane.doe@okhdfcbank", valid: true, account_holder_name: "Jane Doe", bank_name: "HDFC Bank" },
    });
  });

  it("returns 200 with valid=false and a reason for a VPA that cannot be used", async () => {
    const response = await api.post("/api/v1/vpa-validations", { vpa: "ghost.notfound@okaxis" });

    expect(response.status).toBe(200);
    expect(response.body.data).toMatchObject({ valid: false, reason: "VPA does not exist" });
    expect(response.body.data).not.toHaveProperty("account_holder_name");
  });

  it("returns valid=false for a handle that is not supported", async () => {
    const response = await api.post("/api/v1/vpa-validations", { vpa: "jane@nobank" });

    expect(response.status).toBe(200);
    expect(response.body.data).toMatchObject({ valid: false, reason: "Unsupported UPI handle '@nobank'" });
  });

  it("returns 400 for a badly formed VPA, since the request itself is invalid", async () => {
    const response = await api.post("/api/v1/vpa-validations", { vpa: "nonsense" });

    expect(response.status).toBe(400);
    expect(response.body.errors[0].field).toBe("vpa");
  });

  it("returns 400 when vpa is missing", async () => {
    const response = await api.post("/api/v1/vpa-validations", {});

    expect(response.status).toBe(400);
    expect(response.body.errors[0].field).toBe("vpa");
  });
});

describe("service endpoints", () => {
  it("reports health", async () => {
    const response = await api.get("/health");

    expect(response.status).toBe(200);
    expect(response.body.status).toBe("ok");
    expect(response.body.service).toBe("upi-payment-service");
    expect(response.body.handles).toContain("okaxis");
  });

  it("returns the standard error shape for unknown routes", async () => {
    const response = await api.get("/nope");

    expect(response.status).toBe(404);
    expect(response.body).toEqual({ success: false, message: "Route GET /nope not found" });
  });

  it("does not run unsupported methods", async () => {
    const response = await fetch(`${api.baseUrl}/api/v1/payments`, { method: "DELETE" });

    expect(response.status).toBe(404);
  });
});

describe("API spec", () => {
  it("is served at /openapi and /openapi.json", async () => {
    const one = await api.get("/openapi");
    const two = await api.get("/openapi.json");

    expect(one.status).toBe(200);
    expect(one.body.openapi).toMatch(/^3\.1/);
    expect(two.body).toEqual(one.body);
  });

  it("matches the committed openapi.json, so a changed contract must be exported", () => {
    expect(readFileSync(SPEC_PATH, "utf8")).toBe(renderSpec());
  });

  it("describes every route the service handles", async () => {
    const document = (await api.get("/openapi")).body;

    for (const route of routes) {
      const path = route.path;
      expect(document.paths[path]?.[route.method], `${route.method} ${path}`).toBeDefined();
    }
    expect(Object.keys(document.paths)).toHaveLength(new Set(routes.map((route) => route.path)).size);
  });

  it("uses 400 for validation errors and has an operationId for every operation", () => {
    const document = buildOpenApiDocument() as any;

    for (const [path, item] of Object.entries<any>(document.paths)) {
      for (const [method, operation] of Object.entries<any>(item)) {
        expect(operation.operationId, `${method} ${path}`).toEqual(expect.any(String));
        expect(operation.responses).not.toHaveProperty("422");
      }
    }
    expect(document.paths["/api/v1/payments"].post.responses).toHaveProperty("400");
    expect(document.paths["/api/v1/payments"].post.responses).toHaveProperty("409");
  });

  it("has an Express path for every contract path", () => {
    expect(toExpressPath("/api/v1/payments/{transaction_id}")).toBe("/api/v1/payments/:transaction_id");
  });

  it("serves the documentation page, without needing the internet", async () => {
    const response = await api.get("/docs/");

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/html");
    expect(response.body).toContain("swagger-ui");
    expect(response.body).not.toMatch(/(src|href)="https?:\/\//);
  });

  it("redirects / to the documentation page", async () => {
    const response = await fetch(`${api.baseUrl}/`, { redirect: "manual" });

    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe("/docs");
  });
});
