import type { Method, TxnStatus } from "../api/types";

export const METHODS: Method[] = ["CARD", "UPI", "NETBANKING"];
export const STATUSES: TxnStatus[] = ["SUCCESS", "PENDING", "FAILED", "EXPIRED", "CANCELLED"];

export const METHOD_LABEL: Record<Method, string> = { CARD: "Card", UPI: "UPI", NETBANKING: "Netbanking" };

// The netbanking mock's bank list (first four letters of the IFSC). BKID is reported as down.
export const BANKS: { code: string; name: string; down?: boolean }[] = [
  { code: "SBIN", name: "State Bank of India" },
  { code: "HDFC", name: "HDFC Bank" },
  { code: "ICIC", name: "ICICI Bank" },
  { code: "UTIB", name: "Axis Bank" },
  { code: "KKBK", name: "Kotak Mahindra Bank" },
  { code: "PUNB", name: "Punjab National Bank" },
  { code: "BARB", name: "Bank of Baroda" },
  { code: "YESB", name: "Yes Bank" },
  { code: "INDB", name: "IndusInd Bank" },
  { code: "CNRB", name: "Canara Bank" },
  { code: "UBIN", name: "Union Bank of India" },
  { code: "IDFB", name: "IDFC FIRST Bank" },
  { code: "FDRL", name: "Federal Bank" },
  { code: "BKID", name: "Bank of India", down: true },
  { code: "IBKL", name: "IDBI Bank" },
  { code: "CBIN", name: "Central Bank of India" },
];

// Test inputs for the mock rails. See the README of each service.
export const TEST_CARDS = [
  { label: "Visa · approved", number: "4111111111111111", cvv: "123", type: "credit" as const },
  { label: "Mastercard · approved", number: "5555555555554444", cvv: "123", type: "credit" as const },
  { label: "RuPay · approved", number: "6074840000000015", cvv: "123", type: "credit" as const },
  { label: "Amex · approved", number: "378282246310005", cvv: "1234", type: "credit" as const },
  { label: "Visa debit · approved", number: "4111111111111111", cvv: "123", type: "debit" as const },
  { label: "Insufficient funds", number: "4111110000000070", cvv: "123", type: "credit" as const },
  { label: "Declined by issuer", number: "4111110000000088", cvv: "123", type: "credit" as const },
  { label: "Incorrect CVV", number: "4111111111111111", cvv: "000", type: "credit" as const },
];

export const TEST_VPAS = [
  { label: "Success", vpa: "jane.doe@okaxis" },
  { label: "Insufficient funds", vpa: "insufficient.funds@okaxis" },
  { label: "Payer declines", vpa: "declined@ybl" },
  { label: "Wrong PIN", vpa: "pinfail@ybl" },
  { label: "Bank down", vpa: "bankdown@oksbi" },
  { label: "Expires", vpa: "expired.user@paytm" },
];

export const TEST_NETBANKING_LOGINS = "Any customer ID succeeds. Try `insufficient`, `declined`, `timeout`, `locked` or `limit` to fail, or press Cancel.";
