/**
 * The mock bank and payer: decides how a collect request will end.
 *
 * Open/Closed: the decision is a list of `OutcomeRule`s checked in order. The first rule
 * that returns an outcome wins. If none does, the payment succeeds. To add a scenario,
 * write a new rule and add it to the list. `UpiOutcomeService` does not change.
 */

import type { FailureCode, Outcome } from "../models/payment.js";
import { toPaise } from "../utils/amount.js";
import type { ParsedVpa } from "../utils/vpa.js";

export interface UpiAttempt {
  payer: ParsedVpa;
  amountPaise: bigint;
}

export interface OutcomeRule {
  /** An outcome, or null when this rule has no objection. */
  evaluate(attempt: UpiAttempt): Outcome | null;
}

/** The mock bank declines payments above its transaction limit. */
export class AmountLimitRule implements OutcomeRule {
  private readonly limitPaise: bigint;

  constructor(limit: string) {
    this.limitPaise = toPaise(limit);
  }

  evaluate(attempt: UpiAttempt): Outcome | null {
    if (attempt.amountPaise > this.limitPaise) {
      return failed("LIMIT_EXCEEDED", "Transaction limit exceeded");
    }
    return null;
  }
}

interface Scenario {
  keyword: string;
  outcome: Outcome;
}

/**
 * A keyword inside the payer's VPA name picks the scenario, for example
 * `insufficient.funds@okaxis`. VPAs with no keyword are approved.
 */
export class PayerScenarioRule implements OutcomeRule {
  static readonly DEFAULT_SCENARIOS: readonly Scenario[] = [
    { keyword: "insufficient", outcome: failed("INSUFFICIENT_FUNDS", "Insufficient funds") },
    { keyword: "declined", outcome: failed("PAYER_DECLINED", "Payer declined the collect request") },
    { keyword: "pinfail", outcome: failed("INCORRECT_PIN", "Incorrect UPI PIN") },
    { keyword: "bankdown", outcome: failed("BANK_UNAVAILABLE", "Payer's bank is unavailable") },
    { keyword: "blocked", outcome: failed("VPA_BLOCKED", "Payer VPA is blocked") },
    {
      keyword: "expired",
      outcome: {
        status: "EXPIRED",
        failureCode: "COLLECT_EXPIRED",
        failureReason: "Payer did not respond before the request expired",
      },
    },
  ];

  private readonly scenarios: readonly Scenario[];

  constructor(scenarios: readonly Scenario[] = PayerScenarioRule.DEFAULT_SCENARIOS) {
    this.scenarios = scenarios;
  }

  evaluate(attempt: UpiAttempt): Outcome | null {
    const match = this.scenarios.find((scenario) => attempt.payer.local.includes(scenario.keyword));
    return match === undefined ? null : { ...match.outcome };
  }
}

export function defaultOutcomeRules(transactionLimit: string): OutcomeRule[] {
  return [new AmountLimitRule(transactionLimit), new PayerScenarioRule()];
}

export class UpiOutcomeService {
  private readonly rules: readonly OutcomeRule[];

  constructor(rules: readonly OutcomeRule[]) {
    this.rules = rules;
  }

  decide(attempt: UpiAttempt): Outcome {
    for (const rule of this.rules) {
      const outcome = rule.evaluate(attempt);
      if (outcome !== null) {
        return outcome;
      }
    }
    return { status: "SUCCESS" };
  }
}

function failed(failureCode: FailureCode, failureReason: string): Outcome {
  return { status: "FAILED", failureCode, failureReason };
}
