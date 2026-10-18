import type { Outcome } from "../models/payment.js";

/**
 * Decides when the payer "responds".
 *
 * Approvals and failures arrive after a short delay, like a person opening their UPI app
 * and entering a PIN. An expiry happens only when the collect request times out.
 */
export class ResolutionPolicy {
  private readonly approvalDelayMs: number;

  constructor(approvalDelayMs: number) {
    this.approvalDelayMs = approvalDelayMs;
  }

  resolvesAt(outcome: Outcome, createdAt: Date, expiresAt: Date): Date {
    if (outcome.status === "EXPIRED") {
      return expiresAt;
    }
    const respondedAt = createdAt.getTime() + this.approvalDelayMs;
    return new Date(Math.min(respondedAt, expiresAt.getTime()));
  }
}
