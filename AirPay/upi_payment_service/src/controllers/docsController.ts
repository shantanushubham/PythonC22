/**
 * Serves the API spec and its documentation page.
 *
 * - `/docs` is Swagger UI. Its files are bundled with the service, so it works offline.
 * - `/openapi` and `/openapi.json` return the raw OpenAPI document.
 * - `/` redirects to `/docs`.
 *
 * None of these are listed in the spec itself.
 */

import { Router } from "express";
import swaggerUi from "swagger-ui-express";

export function docsRouter(document: object): Router {
  const router = Router();

  router.get("/", (_req, res) => {
    res.redirect("/docs");
  });

  router.get(["/openapi", "/openapi.json"], (_req, res) => {
    res.json(document);
  });

  router.use(
    "/docs",
    swaggerUi.serve,
    swaggerUi.setup(document as swaggerUi.JsonObject, {
      customSiteTitle: "UPI Payment Service",
    }),
  );

  return router;
}
