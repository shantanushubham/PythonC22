import { useEffect, useRef } from "react";
import { getMyTransaction } from "../api/endpoints";
import type { Transaction } from "../api/types";
import { dayKey, fromPaise, toPaise, titleCase } from "./format";

export function instrumentLabel(txn: Transaction): string {
  const i = txn.instrument ?? {};
  if (txn.method === "CARD") {
    const brand = i.network ? titleCase(i.network.replace("_", " ")) : "Card";
    return `${brand}${i.card_type ? ` ${i.card_type}` : ""} ••${i.last_four ?? "????"}`;
  }
  if (txn.method === "UPI") return i.payer_vpa ?? "UPI";
  return i.bank_name ?? i.bank_code ?? "Netbanking";
}

export interface TxnStats {
  count: number;
  success: number;
  failed: number;
  pending: number;
  successRate: number | null;
  grossPaise: number;
  commissionPaise: number;
  netPaise: number;
  avgPaise: number;
}

export function computeStats(txns: Transaction[]): TxnStats {
  let success = 0, failed = 0, pending = 0, gross = 0, commission = 0, net = 0;
  for (const t of txns) {
    if (t.status === "SUCCESS") {
      success++;
      gross += toPaise(t.amount);
      commission += toPaise(t.commission);
      net += toPaise(t.net_amount ?? t.amount);
    } else if (t.status === "PENDING") pending++;
    else failed++; // FAILED, EXPIRED, CANCELLED
  }
  const finished = success + failed;
  return {
    count: txns.length,
    success,
    failed,
    pending,
    successRate: finished ? (success / finished) * 100 : null,
    grossPaise: gross,
    commissionPaise: commission,
    netPaise: net,
    avgPaise: success ? Math.round(gross / success) : 0,
  };
}

/** Successful volume per day for the last `days` days, oldest first. */
export function dailyVolume(txns: Transaction[], days = 14) {
  const buckets = new Map<string, { date: Date; gross: number; net: number; count: number }>();
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    buckets.set(dayKey(d), { date: d, gross: 0, net: 0, count: 0 });
  }
  for (const t of txns) {
    if (t.status !== "SUCCESS") continue;
    const bucket = buckets.get(dayKey(new Date(t.created_at)));
    if (!bucket) continue;
    bucket.gross += toPaise(t.amount);
    bucket.net += toPaise(t.net_amount ?? t.amount);
    bucket.count++;
  }
  return [...buckets.values()].map((b) => ({
    label: b.date.toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
    gross: Number(fromPaise(b.gross)),
    net: Number(fromPaise(b.net)),
    count: b.count,
  }));
}

export function methodBreakdown(txns: Transaction[]) {
  const totals: Record<string, { value: number; count: number }> = {};
  for (const t of txns) {
    if (t.status !== "SUCCESS") continue;
    const entry = (totals[t.method] ??= { value: 0, count: 0 });
    entry.value += toPaise(t.amount);
    entry.count++;
  }
  return Object.entries(totals).map(([method, v]) => ({ method, value: Number(fromPaise(v.value)), count: v.count }));
}

/**
 * UPI and netbanking payments start PENDING. The list endpoint does not ask the rail again,
 * but the detail endpoint does (and credits the wallet on success). So while something is
 * pending, ask about each one every few seconds and call `onChange` when one has finished.
 */
export function usePendingSync(txns: Transaction[] | undefined, onChange: () => void, intervalMs = 5000) {
  const changeRef = useRef(onChange);
  changeRef.current = onChange;
  const pendingIds = (txns ?? []).filter((t) => t.status === "PENDING").slice(0, 10).map((t) => t.id);
  const signature = pendingIds.join(",");

  useEffect(() => {
    if (!signature) return;
    const ids = signature.split(",");
    let stopped = false;
    const controller = new AbortController();

    const tick = async () => {
      const results = await Promise.allSettled(ids.map((id) => getMyTransaction(id, controller.signal)));
      if (stopped) return;
      if (results.some((r) => r.status === "fulfilled" && r.value.status !== "PENDING")) changeRef.current();
    };

    void tick();
    const timer = setInterval(tick, intervalMs);
    return () => {
      stopped = true;
      controller.abort();
      clearInterval(timer);
    };
  }, [signature, intervalMs]);
}
