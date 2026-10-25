import { useNavigate } from "react-router-dom";
import type { Transaction } from "../api/types";
import { formatDateShort, formatMoney } from "../lib/format";
import { instrumentLabel } from "../lib/txn";
import { MethodBadge, RefundBadge, StatusBadge } from "./ui";

export function TransactionTable({ txns, compact = false }: { txns: Transaction[]; compact?: boolean }) {
  const navigate = useNavigate();
  return (
    <div className="table-wrap">
      <table className="table table-click">
        <thead>
          <tr>
            <th>Date</th>
            <th>Method</th>
            <th>Payer</th>
            <th className="num">Amount</th>
            {!compact && <th className="num">Net</th>}
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {txns.map((t) => (
            <tr
              key={t.id}
              tabIndex={0}
              onClick={() => navigate(`/transactions/${t.id}`)}
              onKeyDown={(e) => e.key === "Enter" && navigate(`/transactions/${t.id}`)}
            >
              <td className="nowrap">{formatDateShort(t.created_at)}</td>
              <td>
                <MethodBadge method={t.method} />
              </td>
              <td>
                {instrumentLabel(t)}
                {!compact && t.reference && <small className="muted block mono">{t.reference}</small>}
              </td>
              <td className="num strong">{formatMoney(t.amount)}</td>
              {!compact && <td className="num">{t.net_amount ? formatMoney(t.net_amount) : <span className="muted">—</span>}</td>}
              <td>
                <StatusBadge status={t.status} />
                {t.refund_status !== "NONE" && <small className="block"><RefundBadge state={t.refund_status} /></small>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
