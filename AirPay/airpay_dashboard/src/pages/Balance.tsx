import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import * as api from "../api/endpoints";
import type { SettleResult } from "../api/types";
import { AccountSelect, defaultAccountId } from "../components/AccountSelect";
import { Alert, Button, Card, EmptyState, ErrorState, Field, PageHeader, Spinner, Stat } from "../components/ui";
import { formatDateShort, formatMoney, toPaise } from "../lib/format";
import { useFetch } from "../lib/useFetch";

export default function Balance() {
  const balance = useFetch((s) => api.getBalance(s));
  const accounts = useFetch((s) => api.listBankAccounts(s));
  const settlements = useFetch((s) => api.listSettlements(s));

  const [accountId, setAccountId] = useState("");
  const [all, setAll] = useState(true);
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string>();
  const [done, setDone] = useState<SettleResult>();

  useEffect(() => {
    if (!accountId || !accounts.data?.some((a) => a.id === accountId)) setAccountId(defaultAccountId(accounts.data));
  }, [accounts.data, accountId]);

  const unsettled = toPaise(balance.data?.unsettled);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setFormError(undefined);
    setDone(undefined);
    try {
      const result = await api.settle({ bank_account_id: accountId, ...(all ? {} : { amount: amount.trim() }) });
      setDone(result);
      balance.setData({ currency: result.currency, unsettled: result.unsettled, settled: result.settled, total: result.total });
      setAmount("");
      void settlements.reload(true);
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) {
        setErrors(err.fieldMap);
        const other = err.errors.filter((x) => !["amount", "bank_account_id"].includes(x.field));
        if (other.length) setFormError(other.map((x) => x.message).join(" · "));
      } else setFormError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Balance & settlements" subtitle="Settling moves money from unsettled to settled, ready for a bank payout." actions={<Button icon="refresh" onClick={() => { void balance.reload(true); void settlements.reload(true); }}>Refresh</Button>} />

      {balance.error && !balance.data ? (
        <Card><ErrorState error={balance.error} onRetry={() => void balance.reload()} /></Card>
      ) : !balance.data ? (
        <Spinner />
      ) : (
        <div className="grid-3">
          <Card className="balance-card balance-unsettled"><Stat label="Unsettled" value={formatMoney(balance.data.unsettled)} hint="From successful collections, after commission" /></Card>
          <Card className="balance-card balance-settled"><Stat label="Settled" value={formatMoney(balance.data.settled)} hint={<Link to="/payouts">Pay this out →</Link>} /></Card>
          <Card className="balance-card"><Stat label="Total" value={formatMoney(balance.data.total)} /></Card>
        </div>
      )}

      <div className="grid-2-1">
        <Card title="Settlement history" pad={false}>
          {settlements.error && !settlements.data ? (
            <ErrorState error={settlements.error} onRetry={() => void settlements.reload()} />
          ) : !settlements.data ? (
            <Spinner />
          ) : settlements.data.length === 0 ? (
            <EmptyState icon="wallet" title="No settlements yet">Settle your unsettled balance to see it here.</EmptyState>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Date</th><th>Settled to</th><th>IFSC</th><th className="num">Amount</th></tr></thead>
                <tbody>
                  {settlements.data.map((s) => (
                    <tr key={s.id}>
                      <td className="nowrap">{formatDateShort(s.created_at)}</td>
                      <td>{s.bank_account.account_holder_name} <span className="muted">••{s.bank_account.account_number_last_four}</span></td>
                      <td className="mono">{s.bank_account.ifsc}</td>
                      <td className="num strong">{formatMoney(s.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Settle funds">
          {accounts.data && accounts.data.length === 0 ? (
            <EmptyState icon="bank" title="Add a bank account first" action={<Link to="/bank-accounts" className="btn btn-primary btn-md">Add bank account</Link>}>
              You choose which account the money is settled to.
            </EmptyState>
          ) : !accounts.data ? (
            <Spinner />
          ) : (
            <form className="form" onSubmit={submit}>
              <Field label="Settle to" error={errors.bank_account_id}>
                {(id) => <AccountSelect id={id} accounts={accounts.data!} value={accountId} onChange={setAccountId} />}
              </Field>
              <label className="check">
                <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} />
                Settle the whole unsettled balance ({formatMoney(unsettled)})
              </label>
              {!all && (
                <Field label="Amount (₹)" error={errors.amount} hint={`Up to ${formatMoney(unsettled)}`}>
                  {(id) => <input id={id} inputMode="decimal" placeholder="500.00" value={amount} onChange={(e) => setAmount(e.target.value)} />}
                </Field>
              )}
              {formError && <Alert tone="bad">{formError}</Alert>}
              {done && (
                <Alert tone="good">
                  Settled {formatMoney(done.settled_now)}. Settled balance is now {formatMoney(done.settled)}.
                </Alert>
              )}
              <Button type="submit" variant="primary" loading={busy} disabled={!accountId || unsettled <= 0 || (!all && !amount.trim())} className="btn-block">
                {all ? "Settle everything" : "Settle amount"}
              </Button>
              {unsettled <= 0 && <p className="muted small">Nothing to settle right now.</p>}
            </form>
          )}
        </Card>
      </div>
    </>
  );
}
