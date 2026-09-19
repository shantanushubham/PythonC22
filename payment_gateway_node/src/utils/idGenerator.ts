import { v4 as uuidv4 } from "uuid";

export function generateTransactionId(): string {
  return `txn_${uuidv4()}`;
}
