/**
 * Import `z` from here, not from "zod". This adds `.openapi()` to every schema so the same
 * schema validates requests and describes them in the OpenAPI spec.
 */

import { extendZodWithOpenApi } from "@asteasolutions/zod-to-openapi";
import { z } from "zod";

extendZodWithOpenApi(z);

export { z };
