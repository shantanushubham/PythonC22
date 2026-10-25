import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import * as api from "../api/endpoints";
import type { Payout } from "../api/types";
import { AccountSelect, defaultAccountId } from "../components/AccountSelect";
import { Alert, Button, Card, CopyButton, EmptyState, ErrorState, Field, KeyValue, Modal, PageHeader, Spinner, Stat, StatusBadge, useToast } from "../components/ui";
import { formatDateShort, formatDateTime, formatMoney, newKey, toPaise } from "../lib/format";
import { useFetch } from "../lib/useFetch";

function PayoutDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const payout = useFetch(() => api.getPayout(id), [id]);
  const p = payout.data;
  return (
    <Modal title="Payout details" onClose={onClose} footer={<Button onClick={onClose}>Close</Button>}>
      {payout.error && !p ? <ErrorState error={payout.error} onRetry={() => void payout.reload()} /> : !p ? <Spinner /> : (
        <>
          {p.status === "FAILED" && <Alert tone="bad">{p.failure_reason || "The bank declined this transfer."} The amount was returned to your settled balance.</Alert>}
          <KeyValue
            rows={[
              ["Payout ID", <span className="inline"><span className="mono">{p.id}</span><CopyButton value={p.id} /></span>],
              ["Amount", <strong>{formatMoney(p.amount)}</strong>],
              ["Status", <StatusBadge status={p.status} />],
              ["Beneficiary", p.bank_account.account_holder_name],
              ["Account", `••${p.bank_account.account_number_last_four}`],
              ["IFSC", <span className="mono">{p.bank_account.ifsc}</span>],
              ["Bank reference", p.bank_reference ? <span className="mono">{p.bank_reference}</span> : "—"],
              ["Requested", formatDateTime(p.created_at)],
              ["Completed", formatDateTime(p.completed_at)],
            ]}
          />
        </>
      )}
    </Modal>
  );
}

export default function Payouts() {
  const toast = useToast();
  const balance = useFetch((s) => api.getBalance(s));
  const accounts = useFetch((s) => api.listBankAccounts(s));
  const payouts = useFetch((s) => api.listPayouts(s));

  const [accountId, setAccountId] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string>();
  const [outcome, setOutcome] = useState<Payout>();
  const [openId, setOpenId] = useState<string>();
  // The same request keeps the same Idempotency-Key, so a retry cannot pay out twice.
  const attempt = useRef({ signature: "", key: "" });

  useEffect(() => {
    if (!accountId || !accounts.data?.some((a) => a.id === accountId)) setAccountId(defaultAccountId(accounts.data));
  }, [accounts.data, accountId]);

  const settled = toPaise(balance.data?.settled);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setFormError(undefined);
    setOutcome(undefined);
    const body = { amount: amount.trim(), bank_account_id: accountId };
    const signature = JSON.stringify(body);
    if (attempt.current.signature !== signature) attempt.current = { signature, key: newKey() };
    try {
      const payout = await api.requestPayout(body, attempt.current.key);
      attempt.current = { signature: "", key: "" };
      setOutcome(payout);
      setAmount("");
      if (payout.status === "FAILED") toast.error("The bank declined the payout. Your balance was restored.");
      else toast.success(`Paid out ${formatMoney(payout.amount)}.`);
      void balance.reload(true);
      void payouts.reload(true);
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) {
        setErrors(err.fieldMap);
        const other = err.errors.filter((x) => !["amount", "bank_account_id"].includes(x.field));
        if (other.length) setFormError(other.map((x) => x.message).join(" · "));
      } else {
        if (err instanceof ApiError && err.status === 409) attempt.current = { signature: "", key: "" };
        setFormError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Payouts" subtitle="Send your settled balance to a bank account by bank transfer." actions={<Button icon="refresh" onClick={() => { void balance.reload(true); void payouts.reload(true); }}>Refresh</Button>} />

      <div className="grid-2-1">
        <Card title="Payout history" pad={false}>
          {payouts.error && !payouts.data ? (
            <ErrorState error={payouts.error} onRetry={() => void payouts.reload()} />
          ) : !payouts.data ? (
            <Spinner />
          ) : payouts.data.length === 0 ? (
            <EmptyState icon="send" title="No payouts yet">Settle some funds, then request your first payout.</EmptyState>
          ) : (
            <div className="table-wrap">
              <table className="table table-click">
                <thead><tr><th>Date</th><th>To</th><th className="num">Amount</th><th>Status</th></tr></thead>
                <tbody>
                  {payouts.data.map((p) => (
                    <tr key={p.id} tabIndex={0} onClick={() => setOpenId(p.id)} onKeyDown={(e) => e.key === "Enter" && setOpenId(p.id)}>
                      <td className="nowrap">{formatDateShort(p.created_at)}</td>
                      <td>
                        {p.bank_account.account_holder_name} <span className="muted">••{p.bank_account.account_number_last_four}</span>
                        {p.bank_reference && <small className="muted block mono">{p.bank_reference}</small>}
                      </td>
                      <td className="num strong">{formatMoney(p.amount)}</td>
                      <td><StatusBadge status={p.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="stack">
          <Card className="balance-card balance-settled">
            <Stat label="Available to pay out" value={balance.data ? formatMoney(balance.data.settled) : "…"} hint={balance.data && toPaise(balance.data.unsettled) > 0 ? <>{formatMoney(balance.data.unsettled)} more is <Link to="/balance">waiting to be settled</Link></> : undefined} />
          </Card>
          <Card title="Request a payout">
            {accounts.data && accounts.data.length === 0 ? (
              <EmptyState icon="bank" title="Add a bank account first" action={<Link to="/bank-accounts" className="btn btn-primary btn-md">Add bank account</Link>}>
                Payouts are bank transfers to an account you have added.
              </EmptyState>
            ) : !accounts.data ? <Spinner /> : (
              <form className="form" onSubmit={submit}>
                <Field label="Pay out to" error={errors.bank_account_id}>
                  {(id) => <AccountSelect id={id} accounts={accounts.data!} value={accountId} onChange={setAccountId} />}
                </Field>
                <Field label="Amount (₹)" error={errors.amount} hint="Minimum ₹1.00">
                  {(id) => (
                    <div className="input-with-btn">
                      <input id={id} inputMode="decimal" placeholder="500.00" value={amount} onChange={(e) => setAmount(e.target.value)} />
                      <Button size="sm" onClick={() => balance.data && setAmount(balance.data.settled)} disabled={settled <= 0}>Max</Button>
                    </div>
                  )}
                </Field>
                {formError && <Alert tone="bad">{formError}</Alert>}
                {outcome && (
                  outcome.status === "FAILED"
                    ? <Alert tone="bad">Declined: {outcome.failure_reason || "the bank rejected the transfer"}. Your settled balance was restored.</Alert>
                    : <Alert tone="good">Paid out {formatMoney(outcome.amount)}. Bank reference <span className="mono">{outcome.bank_reference}</span>.</Alert>
                )}
                <Button type="submit" variant="primary" loading={busy} disabled={!accountId || !amount.trim()} className="btn-block">Send payout</Button>
                <p className="muted small">This is a mock transfer. Account numbers ending in <code>0000</code> and IFSCs starting with <code>FAIL</code> are declined.</p>
              </form>
            )}
          </Card>
        </div>
      </div>
      {openId && <PayoutDetail id={openId} onClose={() => setOpenId(undefined)} />}
    </>
  );
}
