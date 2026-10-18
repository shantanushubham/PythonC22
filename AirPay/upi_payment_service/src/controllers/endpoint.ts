import type { RouteConfig } from "@asteasolutions/zod-to-openapi";
import type { RequestHandler } from "express";

/** A handler bound to the contract that describes it. */
export interface Endpoint {
  route: RouteConfig;
  handler: RequestHandler;
}
