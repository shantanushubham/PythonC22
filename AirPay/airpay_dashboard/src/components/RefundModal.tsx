import { useRef, useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "../api/client";
import * as api from "../api/endpoints";
import type { Refund, Transaction } from "../api/types";
import { formatMoney, newKey, toPaise } from "../lib/format";
import { commissionToReturn } from "../lib/refund";
import { Alert, Button, Field, KeyValue, Modal } from "./ui";

interface Props {
  txn: Transaction;
  /** Earlier refunds of this payment, used to work out the commission still to be returned. */
  history: Refund[];
  onClose: () => void;
  /** Called after the server answered, whether the refund went through or the bank declined it. */
  onDone: (refund: Refund) => void;
}

const AMOUNT_RE = /^\d+(\.\d{1,2})?$/;

export function RefundModal({ txn, history, onClose, onDone }: Props) {
  const refundablePaise = toPaise(txn.refundable);
  const [mode, setMode] = useState<"full" | "partial">("full");
  const [partial, setPartial] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string>();
  // The same request keeps the same Idempotency-Key, so a retry after a network error cannot refund twice.
  const attempt = useRef({ signature: "", key: "" });

  const returnedSoFar = history.filter((r) => r.status === "SUCCESS").reduce((sum, r) => sum + toPaise(r.commission_returned), 0);
  const typed = partial.trim();
  const partialValid = AMOUNT_RE.test(typed) && toPaise(typed) > 0;
  const amountPaise = mode === "full" ? refundablePaise : partialValid ? toPaise(typed) : 0;
  const tooMuch = amountPaise > refundablePaise;
  const commissionBack = amountPaise > 0 && !tooMuch ? commissionToReturn(txn, amountPaise, returnedSoFar) : 0;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setFormError(undefined);
    // Omit the amount for a full refund, so the server refunds exactly what is left.
    const body = { ...(mode === "partial" ? { amount: typed } : {}), reason: reason.trim() };
    const signature = JSON.stringify(body);
    if (attempt.current.signature !== signature) attempt.current = { signature, key: newKey() };
    try {
      const refund = await api.createRefund(txn.id, body, attempt.current.key);
      attempt.current = { signature: "", key: "" };
      onDone(refund);
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) {
        setErrors(err.fieldMap);
        // In full mode there is no amount field to show the error under, so show it as an alert.
        const shown = mode === "partial" ? ["amount", "reason"] : ["reason"];
        const other = err.errors.filter((x) => !shown.includes(x.field));
        if (other.length) setFormError(other.map((x) => x.message).join(" · "));
      } else {
        if (err instanceof ApiError && (err.status === 409 || err.status === 422)) attempt.current = { signature: "", key: "" };
        setFormError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = amountPaise > 0 && !tooMuch;

  return (
    <Modal
      title="Refund payment"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="refund-form" variant="primary" loading={busy} disabled={!canSubmit}>
            Refund {amountPaise > 0 && !tooMuch ? formatMoney(amountPaise) : ""}
          </Button>
        </>
      }
    >
      <form id="refund-form" className="form" onSubmit={submit}>
        <div className="seg" role="radiogroup" aria-label="Refund type">
          <label className={`seg-item ${mode === "full" ? "seg-on" : ""}`}>
            <input type="radio" name="mode" checked={mode === "full"} onChange={() => setMode("full")} />
            {txn.refund_status === "PARTIAL" ? "Refund the rest" : "Full refund"} · {formatMoney(refundablePaise)}
          </label>
          <label className={`seg-item ${mode === "partial" ? "seg-on" : ""}`}>
            <input type="radio" name="mode" checked={mode === "partial"} onChange={() => setMode("partial")} />
            Part of it
          </label>
        </div>

        {mode === "partial" && (
          <Field
            label="Amount (₹)"
            error={errors.amount ?? (tooMuch ? `You can refund up to ${formatMoney(refundablePaise)}.` : typed && !partialValid ? "Enter an amount such as 250.00" : undefined)}
            hint={`Up to ${formatMoney(refundablePaise)}`}
          >
            {(id) => <input id={id} inputMode="decimal" placeholder="250.00" value={partial} onChange={(e) => setPartial(e.target.value)} />}
          </Field>
        )}

        <Field label="Reason (optional)" error={errors.reason}>
          {(id) => <input id={id} maxLength={200} placeholder="e.g. Customer returned the item" value={reason} onChange={(e) => setReason(e.target.value)} />}
        </Field>

        {canSubmit && (
          <div className="preview">
            <KeyValue
              rows={[
                ["Sent back to the payer", <strong>{formatMoney(amountPaise)}</strong>],
                ["Commission AirPay returns", commissionBack ? `+ ${formatMoney(commissionBack)}` : "—"],
                ["Taken from your balance", <strong>{formatMoney(amountPaise - commissionBack)}</strong>],
              ]}
            />
            <p className="muted small">It is taken from your unsettled balance first, then your settled balance. You can't refund money you have already paid out.</p>
          </div>
        )}

        {formError && <Alert tone="bad">{formError}</Alert>}
        <p className="muted small">
          This is a mock bank: a refund ending in <code>.99</code> is declined, and no money moves.
        </p>
      </form>
    </Modal>
  );
}
