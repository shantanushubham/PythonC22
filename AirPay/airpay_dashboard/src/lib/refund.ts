import type { Refund, Transaction } from "../api/types";
import { toPaise } from "./format";

/**
 * The commission AirPay gives back for refunding `amountPaise` of this payment.
 * This is the same formula as the gateway (payments/refunds.py), so the preview in the
 * refund dialog matches what the server will do: the share is worked out on the running
 * total refunded, rounded half up, minus what was already returned.
 */
export function commissionToReturn(txn: Transaction, amountPaise: number, commissionRefundedPaise: number): number {
  const commission = BigInt(toPaise(txn.commission));
  if (commission === 0n || amountPaise <= 0) return 0;
  const total = BigInt(toPaise(txn.amount));
  const cumulative = BigInt(toPaise(txn.refunded) + amountPaise);
  const due = (2n * commission * cumulative + total) / (2n * total);
  const alreadyReturned = BigInt(commissionRefundedPaise);
  const value = due - alreadyReturned;
  const left = commission - alreadyReturned;
  return Number(value < 0n ? 0n : value > left ? left : value);
}

export interface RefundStats {
  count: number;
  failed: number;
  refundedPaise: number;
  commissionReturnedPaise: number;
  netDebitedPaise: number;
}

/** Totals over refunds that went through. A failed refund moved no money, so it adds nothing. */
export function computeRefundStats(refunds: Refund[]): RefundStats {
  let count = 0, failed = 0, refunded = 0, commission = 0, net = 0;
  for (const r of refunds) {
    if (r.status !== "SUCCESS") {
      failed++;
      continue;
    }
    count++;
    refunded += toPaise(r.amount);
    commission += toPaise(r.commission_returned);
    net += toPaise(r.net_debit);
  }
  return { count, failed, refundedPaise: refunded, commissionReturnedPaise: commission, netDebitedPaise: net };
}
