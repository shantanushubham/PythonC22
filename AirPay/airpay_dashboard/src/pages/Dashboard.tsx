import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import * as api from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { TransactionTable } from "../components/TransactionTable";
import { Alert, Button, Card, EmptyState, ErrorState, Icon, PageHeader, Spinner, Stat, StatusBadge } from "../components/ui";
import { METHOD_LABEL } from "../lib/constants";
import { formatDateTime, formatMoney, formatMoneyCompact, timeAgo } from "../lib/format";
import { computeRefundStats } from "../lib/refund";
import { computeStats, dailyVolume, methodBreakdown, usePendingSync } from "../lib/txn";
import { useFetch } from "../lib/useFetch";
import type { Method } from "../api/types";

const METHOD_COLOR: Record<Method, string> = { CARD: "#6366f1", UPI: "#10b981", NETBANKING: "#f59e0b" };

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tip">
      <strong>{label}</strong>
      {payload.map((p) => (
        <div key={p.name}>
          {p.name}: {formatMoney(Math.round(p.value * 100))}
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { customer } = useAuth();
  const balance = useFetch((s) => api.getBalance(s));
  const txns = useFetch((s) => api.listMyTransactions(s));
  const payouts = useFetch((s) => api.listPayouts(s));
  const refunds = useFetch((s) => api.listRefunds(s));
  const settlements = useFetch((s) => api.listSettlements(s));
  const accounts = useFetch((s) => api.listBankAccounts(s));
  const keys = useFetch((s) => api.listApiKeys(s));

  // A pending UPI or netbanking payment that finishes also changes the balance.
  usePendingSync(txns.data, () => {
    void txns.reload(true);
    void balance.reload(true);
  });

  const stats = useMemo(() => computeStats(txns.data ?? []), [txns.data]);
  const refundStats = useMemo(() => computeRefundStats(refunds.data ?? []), [refunds.data]);
  // Commission and earnings after refunds: AirPay gives commission back, and the payer gets the money.
  const commissionPaise = stats.commissionPaise - refundStats.commissionReturnedPaise;
  const earningsPaise = stats.netPaise - refundStats.netDebitedPaise;
  const daily = useMemo(() => dailyVolume(txns.data ?? [], 14), [txns.data]);
  const byMethod = useMemo(() => methodBreakdown(txns.data ?? []), [txns.data]);

  const activity = useMemo(() => {
    const items = [
      ...(payouts.data ?? []).map((p) => ({ kind: "Payout" as const, id: p.id, at: p.created_at, amount: p.amount, status: p.status, detail: `to ••${p.bank_account.account_number_last_four}` })),
      ...(refunds.data ?? []).map((r) => ({ kind: "Refund" as const, id: r.id, at: r.created_at, amount: r.amount, status: r.status, detail: r.reason || `of ${formatMoney(r.transaction.amount)} payment` })),
      ...(settlements.data ?? []).map((s) => ({ kind: "Settlement" as const, id: s.id, at: s.created_at, amount: s.amount, status: "SUCCESS", detail: `to ••${s.bank_account.account_number_last_four}` })),
    ];
    return items.sort((a, b) => b.at.localeCompare(a.at)).slice(0, 6);
  }, [payouts.data, settlements.data, refunds.data]);

  const needsBank = accounts.data && accounts.data.length === 0;
  const needsKey = keys.data && keys.data.filter((k) => k.status === "active").length === 0;
  const hasData = (txns.data?.length ?? 0) > 0;
  const chartTotal = daily.reduce((sum, d) => sum + d.gross, 0);

  return (
    <>
      <PageHeader
        title={`Hello, ${customer?.first_name ?? "there"}`}
        subtitle={`Here is how ${customer?.company_name ?? "your business"} is doing.`}
        actions={
          <>
            <Link to="/collect" className="btn btn-secondary btn-md">
              <Icon name="card" size={17} /> Collect payment
            </Link>
            <Link to="/balance" className="btn btn-primary btn-md">
              <Icon name="wallet" size={17} /> Settle balance
            </Link>
          </>
        }
      />

      {(needsBank || needsKey) && (
        <div className="stack">
          {needsKey && (
            <Alert tone="info">
              You have no active API key. <Link to="/api-keys">Create one</Link> to take payments from your own app.
            </Alert>
          )}
          {needsBank && (
            <Alert tone="warn">
              Add a bank account to settle and pay out your money. <Link to="/bank-accounts">Add bank account</Link>
            </Alert>
          )}
        </div>
      )}

      <div className="grid-3">
        {balance.loading && !balance.data ? (
          <Card><Spinner /></Card>
        ) : balance.error && !balance.data ? (
          <Card className="span-3"><ErrorState error={balance.error} onRetry={() => void balance.reload()} /></Card>
        ) : (
          <>
            <Card className="balance-card balance-unsettled">
              <Stat label="Unsettled balance" value={formatMoney(balance.data?.unsettled)} hint="Collected, not yet available to pay out" />
              <Link to="/balance" className="link-arrow">Settle <Icon name="arrowRight" size={15} /></Link>
            </Card>
            <Card className="balance-card balance-settled">
              <Stat label="Settled balance" value={formatMoney(balance.data?.settled)} hint="Available for a bank payout" />
              <Link to="/payouts" className="link-arrow">Pay out <Icon name="arrowRight" size={15} /></Link>
            </Card>
            <Card className="balance-card">
              <Stat label="Total balance" value={formatMoney(balance.data?.total)} hint="Settled + unsettled" />
            </Card>
          </>
        )}
      </div>

      <div className="grid-5">
        <Card><Stat label="Gross collected" value={formatMoney(stats.grossPaise)} hint={`${stats.success} successful payment${stats.success === 1 ? "" : "s"}`} /></Card>
        <Card>
          <Stat
            label="Refunded"
            value={formatMoney(refundStats.refundedPaise)}
            tone={refundStats.refundedPaise > 0 ? "warn" : undefined}
            hint={<>{refundStats.count} refund{refundStats.count === 1 ? "" : "s"} · <Link to="/refunds">view</Link></>}
          />
        </Card>
        <Card><Stat label="AirPay commission" value={formatMoney(commissionPaise)} hint={refundStats.commissionReturnedPaise ? `After ${formatMoney(refundStats.commissionReturnedPaise)} returned` : "Deducted from collections"} /></Card>
        <Card><Stat label="Net earnings" value={formatMoney(earningsPaise)} tone="good" hint={refundStats.count ? "After commission and refunds" : stats.success ? `Avg ${formatMoney(stats.avgPaise)} per payment` : undefined} /></Card>
        <Card>
          <Stat
            label="Success rate"
            value={stats.successRate === null ? "—" : `${stats.successRate.toFixed(1)}%`}
            tone={stats.successRate === null ? undefined : stats.successRate >= 80 ? "good" : stats.successRate >= 50 ? "warn" : "bad"}
            hint={`${stats.failed} failed · ${stats.pending} pending`}
          />
        </Card>
      </div>

      {txns.error && !txns.data ? (
        <Card><ErrorState error={txns.error} onRetry={() => void txns.reload()} /></Card>
      ) : txns.loading && !txns.data ? (
        <Card><Spinner label="Loading transactions…" /></Card>
      ) : (
        <>
          <div className="grid-chart">
            <Card title="Collections · last 14 days" actions={<span className="muted">{formatMoney(Math.round(chartTotal * 100))}</span>}>
              {hasData ? (
                <div className="chart">
                  <ResponsiveContainer width="100%" height={260}>
                    <AreaChart data={daily} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="gGross" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0" stopColor="#6366f1" stopOpacity={0.35} />
                          <stop offset="1" stopColor="#6366f1" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="gNet" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0" stopColor="#10b981" stopOpacity={0.3} />
                          <stop offset="1" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="label" tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={24} />
                      <YAxis tickLine={false} axisLine={false} width={56} tickFormatter={(v: number) => formatMoneyCompact(v * 100)} />
                      <Tooltip content={<ChartTooltip />} />
                      <Area type="monotone" dataKey="gross" name="Gross" stroke="#6366f1" strokeWidth={2} fill="url(#gGross)" />
                      <Area type="monotone" dataKey="net" name="Net" stroke="#10b981" strokeWidth={2} fill="url(#gNet)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyState icon="trend" title="No collections yet" action={<Link to="/collect" className="btn btn-primary btn-md">Make a test payment</Link>}>
                  Successful payments will appear here.
                </EmptyState>
              )}
            </Card>

            <Card title="By payment method">
              {byMethod.length ? (
                <>
                  <div className="chart">
                    <ResponsiveContainer width="100%" height={180}>
                      <PieChart>
                        <Pie data={byMethod} dataKey="value" nameKey="method" innerRadius={52} outerRadius={80} paddingAngle={3} stroke="none">
                          {byMethod.map((m) => (
                            <Cell key={m.method} fill={METHOD_COLOR[m.method as Method]} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <ul className="legend">
                    {byMethod.map((m) => (
                      <li key={m.method}>
                        <span className="swatch" style={{ background: METHOD_COLOR[m.method as Method] }} />
                        <span>{METHOD_LABEL[m.method as Method]}</span>
                        <span className="muted">{m.count} payment{m.count === 1 ? "" : "s"}</span>
                        <strong>{formatMoney(Math.round(m.value * 100))}</strong>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <EmptyState icon="card" title="Nothing to show">Collect a payment to see the split.</EmptyState>
              )}
            </Card>
          </div>

          <div className="grid-chart">
            <Card
              title="Recent transactions"
              pad={false}
              actions={<Link to="/transactions" className="link-arrow">View all <Icon name="arrowRight" size={15} /></Link>}
            >
              {hasData ? (
                <TransactionTable txns={(txns.data ?? []).slice(0, 6)} compact />
              ) : (
                <EmptyState title="No transactions yet">Payments you collect with an API key show up here.</EmptyState>
              )}
            </Card>

            <Card title="Settlements, payouts & refunds" pad={false}>
              {activity.length ? (
                <ul className="feed">
                  {activity.map((a) => (
                    <li key={a.kind + a.id}>
                      <div>
                        <strong>{a.kind}</strong> <span className="muted">{a.detail}</span>
                        <small className="muted block">{timeAgo(a.at)} · {formatDateTime(a.at)}</small>
                      </div>
                      <div className="feed-right">
                        <strong>{formatMoney(a.amount)}</strong>
                        <StatusBadge status={a.status} />
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState icon="send" title="No settlements, payouts or refunds yet">
                  Settle your unsettled balance, then pay out to your bank.
                </EmptyState>
              )}
            </Card>
          </div>
        </>
      )}

      <div className="row-end">
        <Button
          size="sm"
          icon="refresh"
          onClick={() => {
            void balance.reload(true);
            void txns.reload(true);
            void payouts.reload(true);
            void refunds.reload(true);
            void settlements.reload(true);
            void accounts.reload(true);
            void keys.reload(true);
          }}
        >
          Refresh
        </Button>
      </div>
    </>
  );
}
