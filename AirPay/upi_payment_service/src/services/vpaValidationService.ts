/**
 * Checks that a VPA can receive a collect request.
 *
 * Open/Closed: supported handles are data (`HandleRegistry`), and extra rules are
 * `VpaCheck` objects. To support a new handle or a new rule, add to the lists in the
 * composition root. `VpaValidationService` does not change.
 */

import { parseVpa, type ParsedVpa } from "../utils/vpa.js";

export interface VpaHandle {
  handle: string;
  bankName: string;
}

export const DEFAULT_HANDLES: readonly VpaHandle[] = [
  { handle: "okaxis", bankName: "Axis Bank" },
  { handle: "oksbi", bankName: "State Bank of India" },
  { handle: "okhdfcbank", bankName: "HDFC Bank" },
  { handle: "okicici", bankName: "ICICI Bank" },
  { handle: "ybl", bankName: "Yes Bank (PhonePe)" },
  { handle: "ibl", bankName: "ICICI Bank (PhonePe)" },
  { handle: "axl", bankName: "Axis Bank (PhonePe)" },
  { handle: "paytm", bankName: "Paytm Payments Bank" },
  { handle: "apl", bankName: "Axis Bank (Amazon Pay)" },
  { handle: "upi", bankName: "BHIM UPI" },
];

export class HandleRegistry {
  private readonly byHandle: Map<string, VpaHandle>;

  constructor(handles: readonly VpaHandle[]) {
    this.byHandle = new Map(handles.map((entry) => [entry.handle, entry]));
  }

  get handles(): string[] {
    return [...this.byHandle.keys()];
  }

  find(handle: string): VpaHandle | undefined {
    return this.byHandle.get(handle);
  }
}

/** One reason a VPA is not usable. Return null when the check has no objection. */
export interface VpaCheck {
  check(vpa: ParsedVpa): string | null;
}

/** The mock bank has no account for VPAs whose name contains "notfound". */
export class UnregisteredVpaCheck implements VpaCheck {
  check(vpa: ParsedVpa): string | null {
    return vpa.local.includes("notfound") ? "VPA does not exist" : null;
  }
}

export function defaultVpaChecks(): VpaCheck[] {
  return [new UnregisteredVpaCheck()];
}

export type VpaValidation =
  | { valid: true; vpa: ParsedVpa; accountHolderName: string; bankName: string }
  | { valid: false; address: string; reason: string };

export class VpaValidationService {
  private readonly handles: HandleRegistry;
  private readonly checks: readonly VpaCheck[];

  constructor(handles: HandleRegistry, checks: readonly VpaCheck[]) {
    this.handles = handles;
    this.checks = checks;
  }

  validate(rawVpa: string): VpaValidation {
    const vpa = parseVpa(rawVpa);
    if (vpa === null) {
      return { valid: false, address: rawVpa.trim().toLowerCase(), reason: "VPA format is invalid" };
    }

    const handle = this.handles.find(vpa.handle);
    if (handle === undefined) {
      return { valid: false, address: vpa.address, reason: `Unsupported UPI handle '@${vpa.handle}'` };
    }

    for (const check of this.checks) {
      const reason = check.check(vpa);
      if (reason !== null) {
        return { valid: false, address: vpa.address, reason };
      }
    }

    return {
      valid: true,
      vpa,
      accountHolderName: holderNameFor(vpa.local),
      bankName: handle.bankName,
    };
  }
}

/** The mock has no real accounts, so the holder name is made up from the VPA: jane.doe -> Jane Doe. */
export function holderNameFor(local: string): string {
  const words = local
    .split(/[._-]+/)
    .map((word) => word.replace(/\d+/g, ""))
    .filter((word) => word.length > 0)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1));
  return words.length > 0 ? words.join(" ") : "UPI User";
}
