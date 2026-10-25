import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../api/endpoints";
import { TransactionTable } from "../components/TransactionTable";
import { Button, Card, EmptyState, ErrorState, Pager, PageHeader, Spinner, Stat } from "../components/ui";
import { METHODS, METHOD_LABEL, STATUSES } from "../lib/constants";
import { downloadCsv, formatMoney } from "../lib/format";
import { computeStats, instrumentLabel, usePendingSync } from "../lib/txn";
import { useFetch } from "../lib/useFetch";
import { titleCase } from "../lib/format";

const PAGE_SIZE = 15;

export default function Transactions() {
  const txns = useFetch((s) => api.listMyTransactions(s));
  const [status, setStatus] = useState("ALL");
  const [method, setMethod] = useState("ALL");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);

  usePendingSync(txns.data, () => void txns.reload(true));

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (txns.data ?? []).filter((t) => {
      if (status !== "ALL" && t.status !== status) return false;
      if (method !== "ALL" && t.method !== method) return false;
      if (!q) return true;
      return [t.id, t.reference, t.description, t.rail_transaction_id, t.rail_reference, instrumentLabel(t), t.amount]
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
  }, [txns.data, status, method, query]);

  const stats = useMemo(() => computeStats(filtered), [filtered]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const visible = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  const counts = useMemo(() => {
    const c: Record<string, number> = { ALL: txns.data?.length ?? 0 };
    for (const t of txns.data ?? []) c[t.status] = (c[t.status] ?? 0) + 1;
    return c;
  }, [txns.data]);

  function exportCsv() {
    downloadCsv("airpay-transactions.csv", [
      ["id", "created_at", "method", "status", "amount", "commission", "net_amount", "refunded", "reference", "payer", "failure_reason"],
      ...filtered.map((t) => [t.id, t.created_at, t.method, t.status, t.amount, t.commission, t.net_amount ?? "", t.refunded, t.reference, instrumentLabel(t), t.failure_reason]),
    ]);
  }

  return (
    <>
      <PageHeader
        title="Transactions"
        subtitle="Every payment collected through AirPay."
        actions={
          <>
            <Button icon="download" onClick={exportCsv} disabled={!filtered.length}>Export CSV</Button>
            <Button icon="refresh" onClick={() => void txns.reload(true)}>Refresh</Button>
            <Link to="/collect" className="btn btn-primary btn-md">New payment</Link>
          </>
        }
      />

      {txns.error && !txns.data ? (
        <Card><ErrorState error={txns.error} onRetry={() => void txns.reload()} /></Card>
      ) : txns.loading && !txns.data ? (
        <Card><Spinner label="Loading transactions…" /></Card>
      ) : (
        <>
          <div className="grid-4">
            <Card><Stat label="Matching payments" value={stats.count} /></Card>
            <Card><Stat label="Gross" value={formatMoney(stats.grossPaise)} /></Card>
            <Card><Stat label="Commission" value={formatMoney(stats.commissionPaise)} /></Card>
            <Card><Stat label="Net" value={formatMoney(stats.netPaise)} tone="good" /></Card>
          </div>

          <Card pad={false}>
            <div className="toolbar">
              <div className="chips" role="tablist" aria-label="Status">
                {["ALL", ...STATUSES].map((s) => (
                  <button key={s} role="tab" aria-selected={status === s} className={`chip ${status === s ? "chip-on" : ""}`} onClick={() => { setStatus(s); setPage(1); }}>
                    {s === "ALL" ? "All" : titleCase(s)} <span className="chip-count">{counts[s] ?? 0}</span>
                  </button>
                ))}
              </div>
              <div className="toolbar-right">
                <select aria-label="Payment method" value={method} onChange={(e) => { setMethod(e.target.value); setPage(1); }}>
                  <option value="ALL">All methods</option>
                  {METHODS.map((m) => <option key={m} value={m}>{METHOD_LABEL[m]}</option>)}
                </select>
                <input type="search" placeholder="Search id, reference, payer…" aria-label="Search" value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} />
              </div>
            </div>
            {visible.length ? (
              <>
                <TransactionTable txns={visible} />
                <Pager page={current} pages={pages} onPage={setPage} total={filtered.length} />
              </>
            ) : (
              <EmptyState title={txns.data?.length ? "No payments match these filters" : "No transactions yet"} action={!txns.data?.length ? <Link to="/collect" className="btn btn-primary btn-md">Collect a test payment</Link> : undefined}>
                {txns.data?.length ? "Try a different status, method or search." : "Payments you collect with an API key will appear here."}
              </EmptyState>
            )}
          </Card>
        </>
      )}
    </>
  );
}
