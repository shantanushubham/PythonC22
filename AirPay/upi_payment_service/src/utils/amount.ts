/**
 * Money is handled as whole paise (BigInt) and as "1500.50" strings. Never as floats.
 */

const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/;

export const MIN_AMOUNT_PAISE = 100n; // Rs 1.00, the smallest UPI payment
export const MAX_AMOUNT_PAISE = 1_000_000_000n; // Rs 10,000,000.00

export function isAmountFormat(value: string): boolean {
  return AMOUNT_PATTERN.test(value);
}

/** "1500.5" -> 150050n. The value must already match the amount format. */
export function toPaise(amount: string): bigint {
  const [whole = "0", fraction = ""] = amount.split(".");
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
}

/** 150050n -> "1500.50" */
export function formatPaise(paise: bigint): string {
  const fraction = (paise % 100n).toString().padStart(2, "0");
  return `${paise / 100n}.${fraction}`;
}

/** "1500.5" -> "1500.50" */
export function canonicalAmount(amount: string): string {
  return formatPaise(toPaise(amount));
}
