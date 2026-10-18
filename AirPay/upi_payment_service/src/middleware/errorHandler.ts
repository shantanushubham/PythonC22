/** Error handlers: turn every failure into the standard error response. */

import type { ErrorRequestHandler, RequestHandler } from "express";
import { ZodError } from "zod";

import { DomainError, type FieldError } from "../errors.js";
import type { Logger } from "../logger.js";

export const notFoundHandler: RequestHandler = (req, res) => {
  res.status(404).json({
    success: false,
    message: `Route ${req.method} ${req.path} not found`,
  });
};

export function errorHandler(logger: Logger): ErrorRequestHandler {
  // Express only treats a function with four parameters as an error handler.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  return (error: unknown, _req, res, _next) => {
    if (error instanceof DomainError) {
      res.status(error.statusCode).json({
        success: false,
        message: error.message,
        ...(error.errors === undefined ? {} : { errors: error.errors }),
      });
      return;
    }

    if (error instanceof ZodError) {
      res.status(400).json({
        success: false,
        message: "Validation failed",
        errors: zodErrorsToFieldErrors(error),
      });
      return;
    }

    const bodyError = bodyParserError(error);
    if (bodyError !== undefined) {
      res.status(bodyError.status).json({ success: false, message: bodyError.message });
      return;
    }

    logger.error("unhandled_error", { error: error instanceof Error ? error.stack : String(error) });
    res.status(500).json({ success: false, message: "Internal server error" });
  };
}

export function zodErrorsToFieldErrors(error: ZodError): FieldError[] {
  const fieldErrors: FieldError[] = [];
  for (const issue of error.issues) {
    const path = issue.path.map(String);
    if (issue.code === "unrecognized_keys") {
      for (const key of issue.keys) {
        fieldErrors.push({ field: [...path, key].join("."), message: "unknown field" });
      }
      continue;
    }
    fieldErrors.push({ field: path.join(".") || "body", message: issue.message });
  }
  return fieldErrors;
}

/** Errors thrown by `express.json()` for bad or oversized bodies. */
function bodyParserError(error: unknown): { status: number; message: string } | undefined {
  if (typeof error !== "object" || error === null || !("type" in error)) {
    return undefined;
  }
  switch (error.type) {
    case "entity.parse.failed":
      return { status: 400, message: "Request body is not valid JSON" };
    case "entity.too.large":
      return { status: 413, message: "Request body is too large" };
    default:
      return undefined;
  }
}
