/**
 * Route contracts: path, request, and responses of every endpoint.
 *
 * Each controller binds its handler to one of these, and the OpenAPI document is built
 * from the same list, so the spec cannot describe an endpoint the service does not have.
 */

import type { RouteConfig } from "@asteasolutions/zod-to-openapi";

import {
  CreatePaymentRequestSchema,
  ErrorResponseSchema,
  GetPaymentParamsSchema,
  HealthResponseSchema,
  PaymentResponseSchema,
  ValidateVpaRequestSchema,
  VpaValidationResponseSchema,
} from "./schemas.js";
import { z } from "./zod.js";

const TXN = "txn_bd87dbbb-c490-42eb-9ba4-a5dd0954f944";

const payer = { vpa: "jane.doe@okaxis", name: "Jane Doe" };
const payee = { vpa: "airpay@okicici", name: "AirPay Merchant" };

const basePayment = {
  transaction_id: TXN,
  amount: "1500.50",
  currency: "INR",
  payer,
  payee,
  rrn: "907497627294",
  description: "Order 1001",
  reference: "order_1001",
  created_at: "2026-10-18T12:13:18.486Z",
  expires_at: "2026-10-18T12:18:18.486Z",
};

const pendingExample = {
  success: true,
  data: { ...basePayment, status: "PENDING" },
};

const successExample = {
  success: true,
  data: { ...basePayment, status: "SUCCESS", completed_at: "2026-10-18T12:13:21.486Z" },
};

const failedExample = {
  success: true,
  data: {
    ...basePayment,
    status: "FAILED",
    failure_code: "INSUFFICIENT_FUNDS",
    failure_reason: "Insufficient funds",
    completed_at: "2026-10-18T12:13:21.486Z",
  },
};

const expiredExample = {
  success: true,
  data: {
    ...basePayment,
    status: "EXPIRED",
    failure_code: "COLLECT_EXPIRED",
    failure_reason: "Payer did not respond before the request expired",
    completed_at: "2026-10-18T12:18:18.486Z",
  },
};

const errorExample = (message: string, errors?: { field: string; message: string }[]) => ({
  success: false,
  message,
  ...(errors === undefined ? {} : { errors }),
});

const serverError = {
  description: "Unexpected server error.",
  content: {
    "application/json": {
      schema: ErrorResponseSchema,
      example: errorExample("Internal server error"),
    },
  },
};

export const createPaymentRoute: RouteConfig = {
  method: "post",
  path: "/api/v1/payments",
  operationId: "createPayment",
  tags: ["payments"],
  summary: "Start a UPI payment (collect request)",
  description:
    "Sends a collect request to the payer's VPA and returns the payment as `PENDING`. " +
    "The payer then approves or rejects it in their UPI app, which the mock simulates after a " +
    "short delay. Poll `GET /api/v1/payments/{transaction_id}` to see the result.\n\n" +
    "Always `201`, even when the payment will later fail. A bad VPA or request is rejected " +
    "with `400` and no payment is created. Repeating a request with the same `Idempotency-Key` " +
    "returns the same payment, in its current state.",
  request: {
    headers: z.object({
      "Idempotency-Key": z.string().optional().openapi({
        description:
          "Optional. Repeating the same key and body returns the original payment instead of " +
          "creating a second one. Using the same key with a different body returns `409`.",
        example: "order-1001-attempt-1",
      }),
    }),
    body: {
      required: true,
      content: { "application/json": { schema: CreatePaymentRequestSchema } },
    },
  },
  responses: {
    201: {
      description: "The collect request was sent. The payment is usually `PENDING`.",
      headers: z.object({
        Location: z.string().optional().openapi({
          description: "Where to poll for the result.",
          example: `/api/v1/payments/${TXN}`,
        }),
        "Idempotent-Replayed": z.literal("true").optional().openapi({
          description: "Present when this is the stored payment from an earlier request with the same Idempotency-Key.",
        }),
      }),
      content: {
        "application/json": {
          schema: PaymentResponseSchema,
          examples: {
            pending: { summary: "Waiting for the payer", value: pendingExample },
          },
        },
      },
    },
    400: {
      description: "The request or the payer VPA was rejected. No payment is created.",
      content: {
        "application/json": {
          schema: ErrorResponseSchema,
          example: errorExample("Validation failed", [
            { field: "payer_vpa", message: "VPA does not exist" },
          ]),
        },
      },
    },
    409: {
      description: "The Idempotency-Key was already used with a different body.",
      content: {
        "application/json": {
          schema: ErrorResponseSchema,
          example: errorExample("Idempotency key was already used with a different request"),
        },
      },
    },
    500: serverError,
  },
};

export const getPaymentRoute: RouteConfig = {
  method: "get",
  path: "/api/v1/payments/{transaction_id}",
  operationId: "getPayment",
  tags: ["payments"],
  summary: "Get the status of a UPI payment",
  description:
    "Returns the payment as it stands now. `PENDING` means the payer has not responded yet, " +
    "so ask again after `Retry-After` seconds. The other statuses are final.\n\n" +
    "`success` is true whenever the payment was found. Read `data.status` for the outcome.",
  request: { params: GetPaymentParamsSchema },
  responses: {
    200: {
      description: "The payment, whatever its status.",
      headers: z.object({
        "Retry-After": z.string().optional().openapi({
          description: "Seconds until it is worth asking again. Present while PENDING.",
          example: "3",
        }),
      }),
      content: {
        "application/json": {
          schema: PaymentResponseSchema,
          examples: {
            pending: { summary: "Waiting for the payer", value: pendingExample },
            success: { summary: "Approved", value: successExample },
            failed: { summary: "Declined", value: failedExample },
            expired: { summary: "Payer never responded", value: expiredExample },
          },
        },
      },
    },
    404: {
      description: "Unknown transaction id.",
      content: {
        "application/json": {
          schema: ErrorResponseSchema,
          example: errorExample("No payment found with id 'txn_missing'"),
        },
      },
    },
    500: serverError,
  },
};

export const validateVpaRoute: RouteConfig = {
  method: "post",
  path: "/api/v1/vpa-validations",
  operationId: "validateVpa",
  tags: ["vpa"],
  summary: "Check that a VPA exists",
  description:
    "Resolves a VPA to the account holder's name, like the check a UPI app does before you pay. " +
    "A well-formed VPA that cannot be used returns `200` with `valid: false` and a `reason`. " +
    "A malformed request returns `400`.",
  request: {
    body: {
      required: true,
      content: { "application/json": { schema: ValidateVpaRequestSchema } },
    },
  },
  responses: {
    200: {
      description: "The result of the check.",
      content: {
        "application/json": {
          schema: VpaValidationResponseSchema,
          examples: {
            valid: {
              summary: "VPA exists",
              value: {
                success: true,
                data: {
                  vpa: "jane.doe@okaxis",
                  valid: true,
                  account_holder_name: "Jane Doe",
                  bank_name: "Axis Bank",
                },
              },
            },
            invalid: {
              summary: "VPA cannot be used",
              value: {
                success: true,
                data: { vpa: "ghost.notfound@okaxis", valid: false, reason: "VPA does not exist" },
              },
            },
          },
        },
      },
    },
    400: {
      description: "The request was malformed.",
      content: {
        "application/json": {
          schema: ErrorResponseSchema,
          example: errorExample("Validation failed", [
            { field: "vpa", message: "VPA must look like name@bank, for example jane.doe@okaxis" },
          ]),
        },
      },
    },
    500: serverError,
  },
};

export const healthRoute: RouteConfig = {
  method: "get",
  path: "/health",
  operationId: "getHealth",
  tags: ["health"],
  summary: "Check the service is running",
  responses: {
    200: {
      description: "The service is up.",
      content: { "application/json": { schema: HealthResponseSchema } },
    },
  },
};

export const routes: readonly RouteConfig[] = [
  createPaymentRoute,
  getPaymentRoute,
  validateVpaRoute,
  healthRoute,
];

/** `/payments/{transaction_id}` -> `/payments/:transaction_id`. */
export function toExpressPath(openApiPath: string): string {
  return openApiPath.replace(/\{(\w+)\}/g, ":$1");
}
