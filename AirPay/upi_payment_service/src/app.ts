import express, { type Express, Router } from "express";

import { buildOpenApiDocument } from "./contracts/openapiDocument.js";
import { routes, toExpressPath } from "./contracts/routes.js";
import { docsRouter } from "./controllers/docsController.js";
import type { Endpoint } from "./controllers/endpoint.js";
import { healthController } from "./controllers/healthController.js";
import { paymentController } from "./controllers/paymentController.js";
import { vpaController } from "./controllers/vpaController.js";
import type { Logger } from "./logger.js";
import { errorHandler, notFoundHandler } from "./middleware/errorHandler.js";
import type { PaymentQueryService } from "./services/paymentQueryService.js";
import type { PaymentService } from "./services/paymentService.js";
import type { VpaValidationService } from "./services/vpaValidationService.js";

export interface AppDependencies {
  payments: PaymentService;
  query: PaymentQueryService;
  vpaValidation: VpaValidationService;
  handles: readonly string[];
  logger: Logger;
}

export function createApp(deps: AppDependencies): Express {
  const app = express();
  app.disable("x-powered-by");
  app.use(express.json({ limit: "16kb" }));

  const endpoints = [
    ...paymentController(deps.payments, deps.query),
    ...vpaController(deps.vpaValidation),
    ...healthController(deps.handles),
  ];
  assertEndpointsMatchContracts(endpoints);

  const api = Router();
  for (const { route, handler } of endpoints) {
    const path = toExpressPath(route.path);
    if (route.method === "get") {
      api.get(path, handler);
    } else if (route.method === "post") {
      api.post(path, handler);
    } else {
      throw new Error(`Unsupported method ${route.method} for ${route.path}`);
    }
  }
  app.use(api);

  app.use(docsRouter(buildOpenApiDocument()));

  app.use(notFoundHandler);
  app.use(errorHandler(deps.logger));
  return app;
}

/** Fails at startup if the spec and the handlers disagree about which endpoints exist. */
function assertEndpointsMatchContracts(endpoints: readonly Endpoint[]): void {
  const bound = new Set(endpoints.map(({ route }) => `${route.method} ${route.path}`));
  const documented = new Set(routes.map((route) => `${route.method} ${route.path}`));

  const unhandled = [...documented].filter((key) => !bound.has(key));
  const undocumented = [...bound].filter((key) => !documented.has(key));
  if (unhandled.length > 0 || undocumented.length > 0) {
    throw new Error(
      `Spec and handlers disagree. No handler: [${unhandled.join(", ")}]. Not in spec: [${undocumented.join(", ")}]`,
    );
  }
}
