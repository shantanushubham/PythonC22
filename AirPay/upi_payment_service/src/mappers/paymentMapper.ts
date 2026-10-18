/** Mappers: build a stored payment, and work out what a caller sees at a given moment. */

import { randomInt, randomUUID } from "node:crypto";

import type { Outcome, Party, PaymentView, UpiPayment } from "../models/payment.js";

export interface NewPaymentInput {
  amount: string;
  payer: Party;
  payee: Party;
  description?: string | undefined;
  reference?: string | undefined;
  outcome: Outcome;
  createdAt: Date;
  expiresAt: Date;
  resolvesAt: Date;
}

export class PaymentMapper {
  toPayment(input: NewPaymentInput): UpiPayment {
    return {
      transactionId: `txn_${randomUUID()}`,
      amount: input.amount,
      currency: "INR",
      payer: input.payer,
      payee: input.payee,
      rrn: randomInt(0, 1_000_000_000_000).toString().padStart(12, "0"),
      description: input.description ?? null,
      reference: input.reference ?? null,
      outcome: input.outcome,
      createdAt: input.createdAt.toISOString(),
      expiresAt: input.expiresAt.toISOString(),
      resolvesAt: input.resolvesAt.toISOString(),
    };
  }

  /** The payment as a caller sees it at `now`: PENDING until the payer responds. */
  toView(payment: UpiPayment, now: Date): PaymentView {
    const resolvesAtMs = Date.parse(payment.resolvesAt);
    const resolved = now.getTime() >= resolvesAtMs;

    const view: PaymentView = {
      transactionId: payment.transactionId,
      status: resolved ? payment.outcome.status : "PENDING",
      amount: payment.amount,
      currency: payment.currency,
      payer: payment.payer,
      payee: payment.payee,
      rrn: payment.rrn,
      createdAt: payment.createdAt,
      expiresAt: payment.expiresAt,
    };

    if (payment.description !== null) view.description = payment.description;
    if (payment.reference !== null) view.reference = payment.reference;

    if (!resolved) {
      view.retryAfterSeconds = Math.max(1, Math.ceil((resolvesAtMs - now.getTime()) / 1000));
      return view;
    }

    view.completedAt = payment.resolvesAt;
    if (payment.outcome.failureCode !== undefined) view.failureCode = payment.outcome.failureCode;
    if (payment.outcome.failureReason !== undefined) view.failureReason = payment.outcome.failureReason;
    return view;
  }
}
