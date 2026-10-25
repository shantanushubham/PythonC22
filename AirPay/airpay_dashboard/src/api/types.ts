// Shapes returned by the AirPay gateway (payment_gateway_django).
// Amounts are strings in rupees, such as "1500.50".

export type Method = "CARD" | "UPI" | "NETBANKING";
export type TxnStatus = "PENDING" | "SUCCESS" | "FAILED" | "EXPIRED" | "CANCELLED";
export type AccountType = "SAVINGS" | "CURRENT";

export interface Customer {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  company_name: string;
  company_address: string;
  date_joined: string;
}

export interface RegisterInput {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  company_name: string;
  company_address: string;
}

export type ProfileUpdate = Partial<
  Pick<Customer, "first_name" | "last_name" | "company_name" | "company_address">
>;

export interface TokenPair {
  access: string;
  refresh: string;
}

export interface APIKey {
  id: string;
  name: string;
  prefix: string;
  last_four: string;
  status: "active" | "revoked" | "expired" | string;
  expires_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

export interface CreatedAPIKey extends APIKey {
  /** The secret. The gateway returns it once. */
  key: string;
}

export interface WhoAmI {
  customer_id: string;
  email: string;
  company_name: string;
  api_key_id: string;
  api_key_prefix: string;
  api_key_expires_at: string;
}

export interface BankAccount {
  id: string;
  account_holder_name: string;
  account_number_last_four: string;
  ifsc: string;
  bank_name: string;
  account_type: AccountType;
  is_default: boolean;
  created_at: string;
}

export interface AddBankAccountInput {
  account_holder_name: string;
  account_number: string;
  ifsc: string;
  bank_name: string;
  account_type: AccountType;
  is_default: boolean;
}

export interface UpdateBankAccountInput {
  account_holder_name?: string;
  bank_name?: string;
  is_default?: boolean;
}

export interface Instrument {
  // card
  last_four?: string;
  network?: string;
  card_type?: string;
  holder_name?: string;
  // upi
  payer_vpa?: string;
  payer_name?: string;
  // netbanking
  bank_code?: string;
  bank_name?: string;
}

export interface Transaction {
  id: string;
  method: Method;
  status: TxnStatus;
  amount: string;
  currency: string;
  reference: string;
  description: string;
  instrument: Instrument;
  rail_transaction_id: string;
  rail_reference: string;
  redirect_url: string;
  failure_reason: string;
  failure_code: string;
  credited: boolean;
  commission: string;
  commission_rate: string;
  net_amount: string | null;
  refunded: string;
  refundable: string;
  refund_status: RefundState;
  created_at: string;
  completed_at: string | null;
}

export type RefundState = "NONE" | "PARTIAL" | "FULL";

export interface Refund {
  id: string;
  transaction_id: string;
  transaction: Pick<Transaction, "id" | "method" | "amount" | "reference" | "instrument">;
  amount: string;
  commission_returned: string;
  /** What actually left the wallet: the refund minus the commission returned. "0.00" if it failed. */
  net_debit: string;
  status: "SUCCESS" | "FAILED";
  reason: string;
  failure_reason: string;
  reference: string;
  created_at: string;
  completed_at: string | null;
}

export interface CreateRefundInput {
  /** Rupees. Leave out to refund everything not yet refunded. */
  amount?: string;
  reason?: string;
}

export interface CardInput {
  card_type: "credit" | "debit";
  number: string;
  expiry_month: number;
  expiry_year: number;
  cvv: string;
  holder_name: string;
}

export interface CreateTransactionInput {
  method: Method;
  amount: string;
  reference?: string;
  description?: string;
  card?: CardInput;
  payer_vpa?: string;
  bank_code?: string;
  return_url?: string;
}

export interface Balance {
  currency: string;
  unsettled: string;
  settled: string;
  total: string;
}

export interface BankSnapshot {
  id: string | null;
  account_holder_name: string;
  account_number_last_four: string;
  ifsc: string;
}

export interface Settlement {
  id: string;
  amount: string;
  bank_account: BankSnapshot;
  created_at: string;
}

export interface SettleResult extends Balance {
  settled_now: string;
  settlement: Settlement | null;
}

export type PayoutStatus = "PENDING" | "SUCCESS" | "FAILED" | string;

export interface Payout {
  id: string;
  amount: string;
  status: PayoutStatus;
  bank_account: BankSnapshot;
  bank_reference: string;
  failure_reason: string;
  created_at: string;
  completed_at: string | null;
}

export interface Health {
  status: string;
  service: string;
  database: string;
}
