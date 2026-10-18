import { validateVpaRoute } from "../contracts/routes.js";
import { ValidateVpaRequestSchema } from "../contracts/schemas.js";
import type { VpaValidationService } from "../services/vpaValidationService.js";
import type { Endpoint } from "./endpoint.js";

export function vpaController(vpaValidation: VpaValidationService): Endpoint[] {
  return [
    {
      route: validateVpaRoute,
      handler: (req, res) => {
        const body = ValidateVpaRequestSchema.parse(req.body);
        const result = vpaValidation.validate(body.vpa);

        const data = result.valid
          ? {
              vpa: result.vpa.address,
              valid: true,
              account_holder_name: result.accountHolderName,
              bank_name: result.bankName,
            }
          : { vpa: result.address, valid: false, reason: result.reason };

        res.status(200).json({ success: true, data });
      },
    },
  ];
}
