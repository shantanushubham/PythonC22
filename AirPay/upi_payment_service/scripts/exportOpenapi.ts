/**
 * Write the OpenAPI spec to openapi.json.
 *
 * Run from the upi_payment_service directory:
 *
 *   npm run openapi
 */

import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { buildOpenApiDocument } from "../src/contracts/openapiDocument.js";

export const SPEC_PATH = fileURLToPath(new URL("../openapi.json", import.meta.url));

export function renderSpec(): string {
  return `${JSON.stringify(buildOpenApiDocument(), null, 2)}\n`;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  writeFileSync(SPEC_PATH, renderSpec());
  console.log(`Wrote ${SPEC_PATH}`);
}
