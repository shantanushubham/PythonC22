/** A VPA (virtual payment address) looks like `jane.doe@okaxis`. */

export interface ParsedVpa {
  /** The full, lower-cased address. */
  address: string;
  local: string;
  handle: string;
}

export const VPA_PATTERN = /^[a-z0-9][a-z0-9._-]{1,49}@[a-z][a-z0-9]{1,29}$/;
export const VPA_FORMAT_MESSAGE = "VPA must look like name@bank, for example jane.doe@okaxis";

export function parseVpa(raw: string): ParsedVpa | null {
  const address = raw.trim().toLowerCase();
  if (!VPA_PATTERN.test(address)) {
    return null;
  }
  const [local = "", handle = ""] = address.split("@");
  return { address, local, handle };
}

/** "jane.doe@okaxis" -> "ja***@okaxis". Use this in logs. */
export function maskVpa(address: string): string {
  const [local = "", handle = ""] = address.split("@");
  return `${local.slice(0, 2)}***@${handle}`;
}
