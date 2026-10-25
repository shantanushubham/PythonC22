import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import * as api from "../api/endpoints";
import { RefundModal } from "../components/RefundModal";
import { Alert, Button, Card, CopyButton, ErrorState, Icon, KeyValue, MethodBadge, PageHeader, RefundBadge, Spinner, StatusBadge, useToast } from "../components/ui";
import { formatDateShort, formatDateTime, formatMoney, toPaise } from "../lib/format";
import { instrumentLabel } from "../lib/txn";
import { useFetch } from "../lib/useFetch";

export default function TransactionDetail() {
  const { id = "" } = useParams();
  // The gateway asks the rail again for a PENDING payment and credits the wallet on success.
  const txn = useFetch((s) => api.getMyTransaction(id, s), [id]);
  const refunds = useFetch((s) => api.listTransactionRefunds(id, s), [id]);
  const toast = useToast();
  const [refunding, setRefunding] = useState(false);
  const pending = txn.data?.status === "PENDING";
  const { reload } = txn;

  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => void reload(true), 4000);
    return () => clearInterval(timer);
  }, [pending, reload]);

  const t = txn.data;

  return (
    <>
      <Link to="/transactions" className="back"><Icon name="arrowLeft" size={16} /> Transactions</Link>
      {txn.error && !t ? (
        <Card><ErrorState error={txn.error} onRetry={() => void txn.reload()} /></Card>
      ) : !t ? (
        <Spinner label="Loading transaction…" />
      ) : (
        <>
          <PageHeader
            title={formatMoney(t.amount)}
            subtitle={
              <span className="inline">
                <MethodBadge method={t.method} /> · {instrumentLabel(t)} · {formatDateTime(t.created_at)}
              </span>
            }
            actions={<><StatusBadge status={t.status} /><RefundBadge state={t.refund_status} /><Button icon="refresh" onClick={() => void txn.reload(true)}>Refresh</Button></>}
          />

          {pending && (
            <Alert tone="info">
              This payment is still pending. {t.method === "NETBANKING" ? "The customer has not finished at the bank yet. " : "Waiting for the payer to approve. "}
              This page checks again every few seconds.
              {t.redirect_url && <> <a href={t.redirect_url} target="_blank" rel="noreferrer">Open the bank page <Icon name="external" size={14} /></a></>}
            </Alert>
          )}
          {(t.status === "FAILED" || t.status === "EXPIRED" || t.status === "CANCELLED") && (
            <Alert tone="bad">{t.failure_reason || `This payment was ${t.status.toLowerCase()}.`}{t.failure_code && <> <code>{t.failure_code}</code></>}</Alert>
          )}
          {t.status === "SUCCESS" && <Alert tone="good">Payment received. {formatMoney(t.net_amount)} was added to your unsettled balance.</Alert>}

          <div className="grid-2-1">
            <Card title="Payment">
              <KeyValue
                rows={[
                  ["Transaction ID", <span className="inline"><span className="mono">{t.id}</span><CopyButton value={t.id} /></span>],
                  ["Status", <StatusBadge status={t.status} />],
                  ["Method", <MethodBadge method={t.method} />],
                  ["Payer / instrument", instrumentLabel(t)],
                  ["Reference", t.reference ? <span className="mono">{t.reference}</span> : "—"],
                  ["Description", t.description || "—"],
                  ["Rail transaction ID", t.rail_transaction_id ? <span className="mono">{t.rail_transaction_id}</span> : "—"],
                  ["Rail reference", t.rail_reference ? <span className="mono">{t.rail_reference}</span> : "—"],
                  ["Created", formatDateTime(t.created_at)],
                  ["Completed", formatDateTime(t.completed_at)],
                ]}
              />
            </Card>

            <Card title="Settlement breakdown">
              <KeyValue
                rows={[
                  ["Amount charged", <strong>{formatMoney(t.amount)}</strong>],
                  [`AirPay commission (${t.commission_rate}%)`, t.credited ? `− ${formatMoney(t.commission)}` : "—"],
                  ["You receive", t.net_amount ? <strong className="good">{formatMoney(t.net_amount)}</strong> : "—"],
                  ["Credited to wallet", t.credited ? "Yes, to unsettled" : "No"],
                  ...(toPaise(t.refunded) > 0 ? ([["Refunded", <span className="bad">− {formatMoney(t.refunded)}</span>]] as [string, React.ReactNode][]) : []),
                ]}
              />
              {!t.credited && <p className="muted small">Commission is charged, and the wallet credited, only when a payment succeeds.</p>}
            </Card>
          </div>

          {t.status === "SUCCESS" && (
            <Card
              title="Refunds"
              pad={false}
              actions={
                toPaise(t.refundable) > 0 ? (
                  <Button size="sm" variant="primary" icon="undo" onClick={() => setRefunding(true)}>Refund</Button>
                ) : undefined
              }
            >
              <div className="refund-summary">
                <div><span className="muted">Refunded</span><strong>{formatMoney(t.refunded)}</strong></div>
                <div><span className="muted">Still refundable</span><strong>{formatMoney(t.refundable)}</strong></div>
              </div>
              {refunds.error && !refunds.data ? (
                <ErrorState error={refunds.error} onRetry={() => void refunds.reload()} />
              ) : !refunds.data ? (
                <Spinner />
              ) : refunds.data.length === 0 ? (
                <p className="muted pad">No refunds yet. You can refund all or part of this payment{t.credited ? "" : " once it is credited"}.</p>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Date</th><th>Reason</th><th className="num">Amount</th><th>Status</th></tr></thead>
                    <tbody>
                      {refunds.data.map((r) => (
                        <tr key={r.id}>
                          <td className="nowrap">{formatDateShort(r.created_at)}</td>
                          <td>
                            {r.reason || <span className="muted">—</span>}
                            {r.status === "FAILED" ? <small className="bad block">{r.failure_reason}</small> : <small className="muted block mono">{r.reference}</small>}
                          </td>
                          <td className="num strong">{formatMoney(r.amount)}</td>
                          <td><StatusBadge status={r.status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {refunding && (
            <RefundModal
              txn={t}
              history={refunds.data ?? []}
              onClose={() => setRefunding(false)}
              onDone={(refund) => {
                setRefunding(false);
                if (refund.status === "FAILED") toast.error(`${refund.failure_reason || "The refund was declined"}. No money moved.`);
                else toast.success(`Refunded ${formatMoney(refund.amount)}.`);
                void txn.reload(true);
                void refunds.reload(true);
              }}
            />
          )}
        </>
      )}
    </>
  );
}
