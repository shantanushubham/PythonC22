/** Serializers: the request and response shapes of the HTTP API. */

import type { PaymentView } from "../models/payment.js";
import {
  MAX_AMOUNT_PAISE,
  MIN_AMOUNT_PAISE,
  canonicalAmount,
  isAmountFormat,
  toPaise,
} from "../utils/amount.js";
import { VPA_FORMAT_MESSAGE, VPA_PATTERN } from "../utils/vpa.js";
import { z } from "./zod.js";

// ---- Building blocks -------------------------------------------------------------

function text(field: string) {
  return z.string({
    error: (issue) =>
      issue.input === undefined ? `${field} is required` : `${field} must be a string`,
  });
}

const AMOUNT_HELP = 'amount must be a decimal string such as "1500.50" or a number';

/** "1500.50" or 1500.5 in, canonical "1500.50" out. Between Rs 1 and Rs 1 crore. */
export const AmountSchema = z
  .union([z.string(), z.number()], { error: AMOUNT_HELP })
  .transform((value) => String(value).trim())
  .pipe(
    z
      .string()
      .refine(isAmountFormat, "amount must be a positive number with at most 2 decimal places")
      .refine(
        (value) => !isAmountFormat(value) || toPaise(value) >= MIN_AMOUNT_PAISE,
        "amount must be at least 1.00",
      )
      .refine(
        (value) => !isAmountFormat(value) || toPaise(value) <= MAX_AMOUNT_PAISE,
        "amount must not exceed 10000000.00",
      ),
  )
  .transform(canonicalAmount);

export const VpaSchema = text("vpa")
  .trim()
  .toLowerCase()
  .regex(VPA_PATTERN, VPA_FORMAT_MESSAGE);

// ---- Requests --------------------------------------------------------------------

export const CreatePaymentRequestSchema = z
  .strictObject({
    amount: AmountSchema.openapi({
      type: "string",
      description:
        'Amount in rupees with at most 2 decimal places. A string ("1500.50") or a JSON number is accepted.',
      example: "1500.50",
    }),
    currency: z.literal("INR").default("INR"),
    payer_vpa: VpaSchema.openapi({
      description:
        "The VPA the collect request is sent to. Upper case is accepted and stored in lower case.",
      example: "jane.doe@okaxis",
    }),
    description: text("description")
      .trim()
      .min(1, "description cannot be empty")
      .max(50, "description must be at most 50 characters")
      .regex(/^[^\u0000-\u001f]+$/, "description must not contain control characters")
      .optional()
      .openapi({ description: "Note shown to the payer in their UPI app.", example: "Order 1001" }),
    reference: text("reference")
      .trim()
      .max(64, "reference must be at most 64 characters")
      .regex(/^[A-Za-z0-9_-]+$/, "reference may only use letters, digits, - and _")
      .optional()
      .openapi({ description: "Your own id for this payment, such as an order id.", example: "order_1001" }),
  })
  .openapi("CreatePaymentRequest");

export const GetPaymentParamsSchema = z.object({
  transaction_id: z.string().min(1).openapi({ example: "txn_bd87dbbb-c490-42eb-9ba4-a5dd0954f944" }),
});

export const ValidateVpaRequestSchema = z
  .strictObject({
    vpa: VpaSchema.openapi({
      description: "The VPA to check. Upper case is accepted and stored in lower case.",
      example: "jane.doe@okaxis",
    }),
  })
  .openapi("ValidateVpaRequest");

// ---- Responses -------------------------------------------------------------------

const PartySchema = z
  .object({
    vpa: z.string().openapi({ example: "jane.doe@okaxis" }),
    name: z.string().openapi({ example: "Jane Doe" }),
  })
  .openapi("Party");

export const PaymentResourceSchema = z
  .object({
    transaction_id: z.string().openapi({ example: "txn_bd87dbbb-c490-42eb-9ba4-a5dd0954f944" }),
    status: z.enum(["PENDING", "SUCCESS", "FAILED", "EXPIRED"]).openapi({
      description:
        "PENDING until the payer responds, then SUCCESS, FAILED, or EXPIRED. Only PENDING can change.",
    }),
    amount: z.string().openapi({ example: "1500.50" }),
    currency: z.literal("INR"),
    payer: PartySchema,
    payee: PartySchema,
    rrn: z.string().openapi({
      description: "12-digit retrieval reference number banks use for the UPI transaction.",
      example: "907497627294",
    }),
    description: z.string().optional(),
    reference: z.string().optional(),
    failure_code: z
      .enum([
        "INSUFFICIENT_FUNDS",
        "PAYER_DECLINED",
        "INCORRECT_PIN",
        "LIMIT_EXCEEDED",
        "BANK_UNAVAILABLE",
        "VPA_BLOCKED",
        "COLLECT_EXPIRED",
      ])
      .optional()
      .openapi({ description: "Machine-readable reason. Present when status is FAILED or EXPIRED." }),
    failure_reason: z.string().optional().openapi({ example: "Insufficient funds" }),
    created_at: z.string().openapi({ example: "2026-10-18T12:13:18.486Z" }),
    expires_at: z.string().openapi({
      description: "When the collect request stops being valid if the payer has not responded.",
      example: "2026-10-18T12:18:18.486Z",
    }),
    completed_at: z.string().optional().openapi({
      description: "When the payer responded. Absent while PENDING.",
      example: "2026-10-18T12:13:21.486Z",
    }),
  })
  .openapi("PaymentResource");

export const PaymentResponseSchema = z
  .object({
    success: z.boolean().openapi({
      description:
        "True when the call worked and `data` describes the payment. Read `data.status` for the outcome.",
    }),
    data: PaymentResourceSchema,
  })
  .openapi("PaymentResponse");

const FieldErrorSchema = z
  .object({ field: z.string(), message: z.string() })
  .openapi("FieldError");

export const ErrorResponseSchema = z
  .object({
    success: z.literal(false),
    message: z.string(),
    errors: z.array(FieldErrorSchema).optional(),
  })
  .openapi("ErrorResponse");

export const VpaValidationResponseSchema = z
  .object({
    success: z.literal(true),
    data: z
      .object({
        vpa: z.string().openapi({ example: "jane.doe@okaxis" }),
        valid: z.boolean(),
        account_holder_name: z.string().optional().openapi({ example: "Jane Doe" }),
        bank_name: z.string().optional().openapi({ example: "Axis Bank" }),
        reason: z.string().optional().openapi({
          description: "Why the VPA cannot be used. Present when `valid` is false.",
          example: "VPA does not exist",
        }),
      })
      .openapi("VpaValidation"),
  })
  .openapi("VpaValidationResponse");

export const HealthResponseSchema = z
  .object({
    status: z.literal("ok"),
    service: z.literal("upi-payment-service"),
    handles: z.array(z.string()).openapi({ description: "UPI handles this service accepts." }),
  })
  .openapi("HealthResponse");

// ---- View -> wire ----------------------------------------------------------------

export type PaymentResource = z.infer<typeof PaymentResourceSchema>;

export function toPaymentResource(view: PaymentView): PaymentResource {
  return {
    transaction_id: view.transactionId,
    status: view.status,
    amount: view.amount,
    currency: view.currency,
    payer: view.payer,
    payee: view.payee,
    rrn: view.rrn,
    description: view.description,
    reference: view.reference,
    failure_code: view.failureCode,
    failure_reason: view.failureReason,
    created_at: view.createdAt,
    expires_at: view.expiresAt,
    completed_at: view.completedAt,
  };
}
