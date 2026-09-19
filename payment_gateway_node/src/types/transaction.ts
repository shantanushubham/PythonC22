export type TransactionType = "credit" | "debit";

export type TransactionStatus = "SUCCESS" | "FAILED" | "PENDING";

export interface BankDetails {
  accountNumber: string;
  ifsc: string;
  accountName: string;
  bankName: string;
}

export interface TransactionRequest extends BankDetails {
  transactionType: TransactionType;
  amount: number;
}

export interface TransactionRecord {
  transactionId: string;
  status: TransactionStatus;
  transactionType: TransactionType;
  amount: number;
  bankDetails: BankDetails;
  failureReason?: string;
  createdAt: string;
  processedAt: string;
}
