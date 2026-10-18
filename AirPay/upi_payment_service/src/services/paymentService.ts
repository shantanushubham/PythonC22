/**
 * Starts a UPI payment by coordinating the other services.
 *
 * This class makes no decisions of its own. VPA validation, the outcome, timing,
 * idempotency, record building, and storage each live in their own class and are passed in
 * (Dependency Inversion). It only runs them in order.
 */

import { RequestValidationError } from "../errors.js";
import type { Logger } from "../logger.js";
import type { PaymentMapper } from "../mappers/paymentMapper.js";
import type { Party, PaymentView } from "../models/payment.js";
import {
  DuplicateIdempotencyKeyError,
  type PaymentRepository,
  type StoredPayment,
} from "../repositories/paymentRepository.js";
import { toPaise } from "../utils/amount.js";
import type { Clock } from "../utils/clock.js";
import { maskVpa } from "../utils/vpa.js";
import type { IdempotencyService } from "./idempotencyService.js";
import type { ResolutionPolicy } from "./resolutionPolicy.js";
import type { UpiOutcomeService } from "./upiOutcomeService.js";
import type { VpaValidationService } from "./vpaValidationService.js";

export interface CreatePaymentCommand {
  /** Canonical amount, such as "1500.50". */
  amount: string;
  payerVpa: string;
  description?: string | undefined;
  reference?: string | undefined;
}

export interface CreatedPayment {
  view: PaymentView;
  /** True when an earlier request with the same Idempotency-Key is being returned. */
  replayed: boolean;
}

export interface PaymentServiceDependencies {
  repository: PaymentRepository;
  vpaValidation: VpaValidationService;
  outcomes: UpiOutcomeService;
  resolution: ResolutionPolicy;
  idempotency: IdempotencyService;
  mapper: PaymentMapper;
  clock: Clock;
  logger: Logger;
  merchant: Party;
  collectExpirySeconds: number;
}

export class PaymentService {
  private readonly deps: PaymentServiceDependencies;

  constructor(deps: PaymentServiceDependencies) {
    this.deps = deps;
  }

  async create(
    command: CreatePaymentCommand,
    rawIdempotencyKey: string | undefined,
  ): Promise<CreatedPayment> {
    const { repository, idempotency } = this.deps;
    const key = idempotency.cleanKey(rawIdempotencyKey);
    const fingerprint = idempotency.fingerprint({
      amount: command.amount,
      payer_vpa: command.payerVpa,
      description: command.description,
      reference: command.reference,
    });

    // Fast path: the key was already used, so replay without validating again.
    if (key !== undefined) {
      const existing = await repository.findByIdempotencyKey(key);
      if (existing !== undefined) {
        return this.replay(existing, fingerprint);
      }
    }

    const { vpaValidation, outcomes, resolution, mapper, clock, merchant } = this.deps;

    const payer = vpaValidation.validate(command.payerVpa);
    if (!payer.valid) {
      throw new RequestValidationError([{ field: "payer_vpa", message: payer.reason }]);
    }

    const createdAt = clock.now();
    const expiresAt = new Date(createdAt.getTime() + this.deps.collectExpirySeconds * 1000);
    const outcome = outcomes.decide({ payer: payer.vpa, amountPaise: toPaise(command.amount) });

    const payment = mapper.toPayment({
      amount: command.amount,
      payer: { vpa: payer.vpa.address, name: payer.accountHolderName },
      payee: merchant,
      description: command.description,
      reference: command.reference,
      outcome,
      createdAt,
      expiresAt,
      resolvesAt: resolution.resolvesAt(outcome, createdAt, expiresAt),
    });

    try {
      await repository.save({ payment, fingerprint, idempotencyKey: key ?? null });
    } catch (error) {
      if (error instanceof DuplicateIdempotencyKeyError && key !== undefined) {
        // Another request saved this key between our check and our save. The repository
        // picked the winner, so return that one.
        const winner = await repository.findByIdempotencyKey(key);
        if (winner !== undefined) {
          return this.replay(winner, fingerprint);
        }
      }
      throw error;
    }

    this.deps.logger.info("payment_created", {
      transaction_id: payment.transactionId,
      payer: maskVpa(payment.payer.vpa),
      amount: payment.amount,
    });
    return { view: mapper.toView(payment, clock.now()), replayed: false };
  }

  private replay(stored: StoredPayment, fingerprint: string): CreatedPayment {
    this.deps.idempotency.ensureSameRequest(stored, fingerprint);
    this.deps.logger.info("payment_replayed", { transaction_id: stored.payment.transactionId });
    return { view: this.deps.mapper.toView(stored.payment, this.deps.clock.now()), replayed: true };
  }
}
