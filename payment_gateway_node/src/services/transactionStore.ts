import { TransactionRecord } from "../types/transaction";

/**
 * Purely in-memory store. No database is used - state is lost on restart.
 * This is intentional; the service only needs to simulate a gateway,
 * not persist data.
 */
class TransactionStore {
  private readonly records = new Map<string, TransactionRecord>();

  save(record: TransactionRecord): void {
    this.records.set(record.transactionId, record);
  }

  findById(transactionId: string): TransactionRecord | undefined {
    return this.records.get(transactionId);
  }
}

export const transactionStore = new TransactionStore();
