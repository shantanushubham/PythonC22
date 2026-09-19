import { TransactionInput } from "../validators/transactionValidator";
import { TransactionRecord } from "../types/transaction";
import { generateTransactionId } from "../utils/idGenerator";
import { transactionStore } from "./transactionStore";

// Simulated gateway failure rate: 25% of all transactions fail.
const FAILURE_RATE = 0.25;

const FAILURE_REASONS = [
  "Insufficient funds",
  "Bank server timeout",
  "Invalid account details",
  "Transaction declined by issuing bank",
  "Daily transaction limit exceeded",
];

function pickRandomFailureReason(): string {
  const index = Math.floor(Math.random() * FAILURE_REASONS.length);
  return FAILURE_REASONS[index];
}

/**
 * Simulates sending the transaction to a bank/payment network.
 * Roughly FAILURE_RATE (25%) of transactions will randomly fail.
 */
export function processTransaction(input: TransactionInput): TransactionRecord {
  const transactionId = generateTransactionId();
  const createdAt = new Date().toISOString();

  const isFailure = Math.random() < FAILURE_RATE;

  const record: TransactionRecord = {
    transactionId,
    status: isFailure ? "FAILED" : "SUCCESS",
    transactionType: input.transactionType,
    amount: input.amount,
    bankDetails: {
      accountNumber: input.accountNumber,
      ifsc: input.ifsc,
      accountName: input.accountName,
      bankName: input.bankName,
    },
    failureReason: isFailure ? pickRandomFailureReason() : undefined,
    createdAt,
    processedAt: new Date().toISOString(),
  };

  transactionStore.save(record);
  return record;
}

export function getTransactionById(transactionId: string): TransactionRecord | undefined {
  return transactionStore.findById(transactionId);
}
