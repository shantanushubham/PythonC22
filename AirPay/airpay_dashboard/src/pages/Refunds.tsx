import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import * as api from "../api/endpoints";
import { Button, Card, EmptyState, ErrorState, Pager, PageHeader, Spinner, Stat, StatusBadge } from "../components/ui";
import { downloadCsv, formatDateShort, formatMoney } from "../lib/format";
import { computeRefundStats } from "../lib/refund";
import { instrumentLabel } from "../lib/txn";
import { useFetch } from "../lib/useFetch";
import type { Transaction } from "../api/types";

const PAGE_SIZE = 15;
const FILTERS = [
  { id: "ALL", label: "All" },
  { id: "SUCCESS", label: "Refunded" },
  { id: "FAILED", label: "Declined" },
];

export default function Refunds() {
  const navigate = useNavigate();
  const refunds = useFetch((s) => api.listRefunds(s));
  const [status, setStatus] = useState("ALL");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (refunds.data ?? []).filter((r) => {
      if (status !== "ALL" && r.status !== status) return false;
      if (!q) return true;
      return [r.id, r.reference, r.reason, r.transaction.reference, r.transaction_id, r.amount].join(" ").toLowerCase().includes(q);
    });
  }, [refunds.data, status, query]);

  const stats = useMemo(() => computeRefundStats(filtered), [filtered]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const visible = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const counts = useMemo(() => {
    const c: Record<string, number> = { ALL: refunds.data?.length ?? 0 };
    for (const r of refunds.data ?? []) c[r.status] = (c[r.status] ?? 0) + 1;
    return c;
  }, [refunds.data]);

  function exportCsv() {
    downloadCsv("airpay-refunds.csv", [
      ["id", "created_at", "transaction_id", "status", "amount", "commission_returned", "net_debit", "reference", "reason", "failure_reason"],
      ...filtered.map((r) => [r.id, r.created_at, r.transaction_id, r.status, r.amount, r.commission_returned, r.net_debit, r.reference, r.reason, r.failure_reason]),
    ]);
  }

  return (
    <>
      <PageHeader
        title="Refunds"
        subtitle={<>Money sent back to payers. To refund a payment, open it from <Link to="/transactions">Transactions</Link>.</>}
        actions={
          <>
            <Button icon="download" onClick={exportCsv} disabled={!filtered.length}>Export CSV</Button>
            <Button icon="refresh" onClick={() => void refunds.reload(true)}>Refresh</Button>
          </>
        }
      />

      {refunds.error && !refunds.data ? (
        <Card><ErrorState error={refunds.error} onRetry={() => void refunds.reload()} /></Card>
      ) : !refunds.data ? (
        <Card><Spinner label="Loading refunds…" /></Card>
      ) : (
        <>
          <div className="grid-4">
            <Card><Stat label="Refunds" value={stats.count} hint={stats.failed ? `${stats.failed} declined` : undefined} /></Card>
            <Card><Stat label="Refunded to payers" value={formatMoney(stats.refundedPaise)} /></Card>
            <Card><Stat label="Commission returned" value={formatMoney(stats.commissionReturnedPaise)} tone="good" hint="Given back by AirPay" /></Card>
            <Card><Stat label="Taken from balance" value={formatMoney(stats.netDebitedPaise)} hint="Refunds minus commission returned" /></Card>
          </div>

          <Card pad={false}>
            <div className="toolbar">
              <div className="chips" role="tablist" aria-label="Status">
                {FILTERS.map((f) => (
                  <button key={f.id} role="tab" aria-selected={status === f.id} className={`chip ${status === f.id ? "chip-on" : ""}`} onClick={() => { setStatus(f.id); setPage(1); }}>
                    {f.label} <span className="chip-count">{counts[f.id] ?? 0}</span>
                  </button>
                ))}
              </div>
              <div className="toolbar-right">
                <input type="search" placeholder="Search reference, reason…" aria-label="Search" value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} />
              </div>
            </div>
            {visible.length ? (
              <>
                <div className="table-wrap">
                  <table className="table table-click">
                    <thead><tr><th>Date</th><th>Payment</th><th className="num">Refunded</th><th className="num">Commission back</th><th>Status</th></tr></thead>
                    <tbody>
                      {visible.map((r) => (
                        <tr key={r.id} tabIndex={0} onClick={() => navigate(`/transactions/${r.transaction_id}`)} onKeyDown={(e) => e.key === "Enter" && navigate(`/transactions/${r.transaction_id}`)}>
                          <td className="nowrap">{formatDateShort(r.created_at)}</td>
                          <td>
                            {instrumentLabel(r.transaction as Transaction)} <span className="muted">of {formatMoney(r.transaction.amount)}</span>
                            {r.status === "FAILED"
                              ? <small className="bad block">{r.failure_reason}</small>
                              : r.reason ? <small className="muted block">{r.reason}</small> : null}
                            {r.reference && <small className="muted block mono">{r.reference}</small>}
                          </td>
                          <td className="num strong">{formatMoney(r.amount)}</td>
                          <td className="num">{r.status === "SUCCESS" && r.commission_returned !== "0.00" ? formatMoney(r.commission_returned) : <span className="muted">—</span>}</td>
                          <td><StatusBadge status={r.status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pager page={current} pages={pages} onPage={setPage} total={filtered.length} />
              </>
            ) : (
              <EmptyState icon="undo" title={refunds.data.length ? "No refunds match these filters" : "No refunds yet"} action={!refunds.data.length ? <Link to="/transactions" className="btn btn-primary btn-md">Go to transactions</Link> : undefined}>
                {refunds.data.length ? "Try a different status or search." : "Open a successful payment and choose Refund to send money back to the payer."}
              </EmptyState>
            )}
          </Card>
        </>
      )}
    </>
  );
}
