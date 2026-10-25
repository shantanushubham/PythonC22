import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as api from "../api/endpoints";
import { Alert, Card, ErrorState, Icon, MethodBadge, PageHeader, Spinner, StatusBadge, KeyValue } from "../components/ui";
import { formatDateTime, formatMoney } from "../lib/format";
import { instrumentLabel } from "../lib/txn";
import { useFetch } from "../lib/useFetch";

/**
 * Where the bank sends the customer back after netbanking. The query string
 * (`transaction_id`, `status`) is only a hint: the customer could have edited it.
 * So the page finds the payment on the gateway and shows what the gateway says.
 */
export default function PayReturn() {
  const [params] = useSearchParams();
  const railId = params.get("transaction_id") ?? "";
  const hint = params.get("status");

  const txn = useFetch(async (signal) => {
    const all = await api.listMyTransactions(signal);
    const match = all.find((t) => t.rail_transaction_id === railId);
    if (!match) throw new Error("We could not find a payment for this link. It may belong to another account.");
    return api.getMyTransaction(match.id, signal); // refreshes a PENDING payment from the bank
  }, [railId]);

  const pending = txn.data?.status === "PENDING";
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => void txn.reload(true), 3000);
    return () => clearInterval(timer);
  }, [pending, txn.reload]);

  const t = txn.data;
  const ok = t?.status === "SUCCESS";

  return (
    <>
      <PageHeader title="Netbanking payment" subtitle="You are back from the bank." />
      {!railId ? (
        <Card><ErrorState error={new Error("This page needs a transaction_id in the link.")} /></Card>
      ) : txn.error && !t ? (
        <Card><ErrorState error={txn.error} onRetry={() => void txn.reload()} /></Card>
      ) : !t ? (
        <Spinner label="Confirming your payment with the gateway…" />
      ) : (
        <Card>
          <div className={`result result-${ok ? "good" : pending ? "pending" : "bad"}`}>
            <div className="result-icon">{pending ? <span className="spinner" /> : <Icon name={ok ? "check" : "x"} size={30} />}</div>
            <h2>{ok ? "Payment successful" : pending ? "Confirming with the bank…" : t.status === "CANCELLED" ? "Payment cancelled" : t.status === "EXPIRED" ? "Payment expired" : "Payment failed"}</h2>
            <p className="result-amount">{formatMoney(t.amount)}</p>
            {t.failure_reason && <p className="muted">{t.failure_reason}</p>}
            {ok && <p className="muted">You receive {formatMoney(t.net_amount)} after {formatMoney(t.commission)} commission.</p>}
          </div>
          {hint && hint.toUpperCase() !== t.status && (
            <Alert tone="warn">The link said <strong>{hint}</strong>, but the gateway reports <strong>{t.status}</strong>. The gateway's answer is the one to trust.</Alert>
          )}
          <KeyValue
            rows={[
              ["Transaction ID", <span className="mono">{t.id}</span>],
              ["Method", <MethodBadge method={t.method} />],
              ["Bank", instrumentLabel(t)],
              ["Status", <StatusBadge status={t.status} />],
              ["Bank reference", t.rail_transaction_id],
              ["Created", formatDateTime(t.created_at)],
            ]}
          />
          <div className="result-actions">
            <Link to={`/transactions/${t.id}`} className="btn btn-secondary btn-md">View details</Link>
            <Link to="/collect" className="btn btn-primary btn-md">New payment</Link>
          </div>
        </Card>
      )}
    </>
  );
}
