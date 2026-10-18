import { OpenAPIRegistry, OpenApiGeneratorV31 } from "@asteasolutions/zod-to-openapi";
import type { RouteConfig } from "@asteasolutions/zod-to-openapi";

import { routes as allRoutes } from "./routes.js";

const DESCRIPTION = `\
Mock UPI service for the AirPay payment gateway.

Start a payment with a payer's VPA (for example \`jane.doe@okaxis\`) and the service sends a
collect request, like a real UPI app would. Nothing reaches a real bank. Payments are saved
to a local SQLite file, so they survive restarts.

### Lifecycle
UPI is asynchronous. \`POST /api/v1/payments\` returns \`PENDING\`. After a short delay
(the payer "approving" in their app) the payment becomes \`SUCCESS\`, \`FAILED\`, or
\`EXPIRED\`. Poll \`GET /api/v1/payments/{transaction_id}\`. The \`Retry-After\` header says
when to ask again.

### Mock scenarios
A keyword inside the **payer VPA name** picks the result. A VPA with no keyword succeeds.

| Keyword in VPA name | Result |
| --- | --- |
| \`notfound\` | Rejected at once with \`400\`, as the VPA does not exist |
| \`insufficient\` | \`FAILED\`, \`INSUFFICIENT_FUNDS\` |
| \`declined\` | \`FAILED\`, \`PAYER_DECLINED\` |
| \`pinfail\` | \`FAILED\`, \`INCORRECT_PIN\` |
| \`bankdown\` | \`FAILED\`, \`BANK_UNAVAILABLE\` |
| \`blocked\` | \`FAILED\`, \`VPA_BLOCKED\` |
| \`expired\` | \`EXPIRED\`, only once the collect request times out |

Amounts above the transaction limit (Rs 1,00,000 by default) fail with \`LIMIT_EXCEEDED\`.
`;

export function buildOpenApiDocument(routes: readonly RouteConfig[] = allRoutes) {
  const registry = new OpenAPIRegistry();
  for (const route of routes) {
    registry.registerPath(route);
  }

  return new OpenApiGeneratorV31(registry.definitions).generateDocument({
    openapi: "3.1.0",
    info: {
      title: "UPI Payment Service",
      version: "1.0.0",
      description: DESCRIPTION,
    },
    servers: [{ url: "http://localhost:8003", description: "Local development" }],
    tags: [
      { name: "payments", description: "Start and track UPI payments." },
      { name: "vpa", description: "Check that a VPA exists." },
      { name: "health", description: "Service liveness." },
    ],
  });
}
