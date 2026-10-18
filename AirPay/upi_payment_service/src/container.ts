/**
 * Composition root: the one place that chooses concrete classes.
 *
 * Everything else depends on interfaces. To change the database, the mock scenarios, or
 * the supported handles, change them here. Tests call `buildDependencies` with their own
 * repository and clock.
 */

import type { AppDependencies } from "./app.js";
import type { Settings } from "./config.js";
import { type Logger } from "./logger.js";
import { PaymentMapper } from "./mappers/paymentMapper.js";
import type { PaymentRepository } from "./repositories/paymentRepository.js";
import { IdempotencyService } from "./services/idempotencyService.js";
import { PaymentQueryService } from "./services/paymentQueryService.js";
import { PaymentService } from "./services/paymentService.js";
import { ResolutionPolicy } from "./services/resolutionPolicy.js";
import {
  UpiOutcomeService,
  defaultOutcomeRules,
  type OutcomeRule,
} from "./services/upiOutcomeService.js";
import {
  DEFAULT_HANDLES,
  HandleRegistry,
  VpaValidationService,
  defaultVpaChecks,
  type VpaCheck,
  type VpaHandle,
} from "./services/vpaValidationService.js";
import { parseVpa } from "./utils/vpa.js";
import type { Clock } from "./utils/clock.js";

export interface BuildOptions {
  settings: Settings;
  repository: PaymentRepository;
  clock: Clock;
  logger: Logger;
  handles?: readonly VpaHandle[];
  vpaChecks?: readonly VpaCheck[];
  outcomeRules?: readonly OutcomeRule[];
}

export function buildDependencies(options: BuildOptions): AppDependencies {
  const { settings, repository, clock, logger } = options;

  const handles = new HandleRegistry(options.handles ?? DEFAULT_HANDLES);
  const vpaValidation = new VpaValidationService(handles, options.vpaChecks ?? defaultVpaChecks());

  const merchantVpa = parseVpa(settings.merchantVpa);
  if (merchantVpa === null || handles.find(merchantVpa.handle) === undefined) {
    throw new Error(`Invalid configuration: UPI_MERCHANT_VPA '${settings.merchantVpa}' is not a usable VPA`);
  }

  const mapper = new PaymentMapper();

  const payments = new PaymentService({
    repository,
    vpaValidation,
    outcomes: new UpiOutcomeService(
      options.outcomeRules ?? defaultOutcomeRules(settings.transactionLimit),
    ),
    resolution: new ResolutionPolicy(settings.approvalDelayMs),
    idempotency: new IdempotencyService(),
    mapper,
    clock,
    logger,
    merchant: { vpa: merchantVpa.address, name: settings.merchantName },
    collectExpirySeconds: settings.collectExpirySeconds,
  });

  return {
    payments,
    query: new PaymentQueryService(repository, mapper, clock),
    vpaValidation,
    handles: handles.handles,
    logger,
  };
}
