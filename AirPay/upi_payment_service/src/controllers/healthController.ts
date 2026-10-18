import { healthRoute } from "../contracts/routes.js";
import type { Endpoint } from "./endpoint.js";

export function healthController(handles: readonly string[]): Endpoint[] {
  return [
    {
      route: healthRoute,
      handler: (_req, res) => {
        res.status(200).json({ status: "ok", service: "upi-payment-service", handles });
      },
    },
  ];
}
