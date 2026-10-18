/**
 * HTTP endpoints for payments.
 *
 * A controller reads the request, calls a service, and turns the result into a response.
 * Business rules live in the services. Errors are thrown by the services and turned into
 * responses by `middleware/errorHandler`, so there is no try/catch here.
 */

import {
  CreatePaymentRequestSchema,
  GetPaymentParamsSchema,
  toPaymentResource,
} from "../contracts/schemas.js";
import { createPaymentRoute, getPaymentRoute } from "../contracts/routes.js";
import type { PaymentQueryService } from "../services/paymentQueryService.js";
import type { PaymentService } from "../services/paymentService.js";
import type { Endpoint } from "./endpoint.js";

export function paymentController(
  payments: PaymentService,
  query: PaymentQueryService,
): Endpoint[] {
  return [
    {
      route: createPaymentRoute,
      handler: async (req, res) => {
        const body = CreatePaymentRequestSchema.parse(req.body);
        const { view, replayed } = await payments.create(
          {
            amount: body.amount,
            payerVpa: body.payer_vpa,
            description: body.description,
            reference: body.reference,
          },
          req.get("Idempotency-Key"),
        );

        if (replayed) {
          res.set("Idempotent-Replayed", "true");
        }
        res
          .status(201)
          .location(`/api/v1/payments/${view.transactionId}`)
          .json({ success: true, data: toPaymentResource(view) });
      },
    },
    {
      route: getPaymentRoute,
      handler: async (req, res) => {
        const { transaction_id } = GetPaymentParamsSchema.parse(req.params);
        const view = await query.get(transaction_id);

        if (view.retryAfterSeconds !== undefined) {
          res.set("Retry-After", String(view.retryAfterSeconds));
        }
        res.status(200).json({ success: true, data: toPaymentResource(view) });
      },
    },
  ];
}
