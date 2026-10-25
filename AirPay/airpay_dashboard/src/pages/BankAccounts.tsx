import { useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "../api/client";
import * as api from "../api/endpoints";
import type { AddBankAccountInput, BankAccount, UpdateBankAccountInput } from "../api/types";
import { Alert, Button, Card, ConfirmDialog, EmptyState, ErrorState, Field, Icon, Modal, PageHeader, Spinner, useToast } from "../components/ui";
import { formatDate } from "../lib/format";
import { useFetch } from "../lib/useFetch";

const ADD_FIELDS = ["account_holder_name", "account_number", "ifsc", "bank_name", "account_type", "is_default"];

function AddModal({ first, onClose, onAdded }: { first: boolean; onClose: () => void; onAdded: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState<AddBankAccountInput>({
    account_holder_name: "",
    account_number: "",
    ifsc: "",
    bank_name: "",
    account_type: "SAVINGS",
    is_default: first,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setFormError(undefined);
    try {
      await api.addBankAccount({ ...form, account_number: form.account_number.replace(/[\s-]/g, ""), ifsc: form.ifsc.trim().toUpperCase() });
      toast.success("Bank account added.");
      onAdded();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) {
        setErrors(err.fieldMap);
        const other = err.errors.filter((x) => !ADD_FIELDS.includes(x.field));
        if (other.length) setFormError(other.map((x) => x.message).join(" · "));
      } else setFormError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Add a bank account"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>Cancel</Button>
          <Button variant="primary" type="submit" form="add-account" loading={busy}>Add account</Button>
        </>
      }
    >
      <form id="add-account" className="form" onSubmit={submit}>
        <Field label="Account holder name" error={errors.account_holder_name}>
          {(id) => <input id={id} required maxLength={150} value={form.account_holder_name} onChange={(e) => setForm({ ...form, account_holder_name: e.target.value })} />}
        </Field>
        <div className="grid-2">
          <Field label="Account number" error={errors.account_number} hint="9 to 18 digits. Stored encrypted.">
            {(id) => <input id={id} required inputMode="numeric" autoComplete="off" value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} />}
          </Field>
          <Field label="IFSC" error={errors.ifsc} hint="For example HDFC0001234">
            {(id) => <input id={id} required maxLength={11} autoComplete="off" value={form.ifsc} onChange={(e) => setForm({ ...form, ifsc: e.target.value.toUpperCase() })} />}
          </Field>
        </div>
        <div className="grid-2">
          <Field label="Bank name" error={errors.bank_name}>
            {(id) => <input id={id} required maxLength={150} value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} />}
          </Field>
          <Field label="Account type" error={errors.account_type}>
            {(id) => (
              <select id={id} value={form.account_type} onChange={(e) => setForm({ ...form, account_type: e.target.value as AddBankAccountInput["account_type"] })}>
                <option value="SAVINGS">Savings</option>
                <option value="CURRENT">Current</option>
              </select>
            )}
          </Field>
        </div>
        <label className="check">
          <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} />
          Use as my default account
        </label>
        {errors.is_default && <Alert tone="bad">{errors.is_default}</Alert>}
        {formError && <Alert tone="bad">{formError}</Alert>}
      </form>
    </Modal>
  );
}

function EditModal({ id, onClose, onSaved }: { id: string; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  // Fetch the account fresh with GET /customers/me/bank-accounts/{id}.
  const account = useFetch(() => api.getBankAccount(id), [id]);
  const a = account.data;
  const [draft, setDraft] = useState<{ holder: string; bank: string; makeDefault: boolean }>();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const values = draft ?? (a ? { holder: a.account_holder_name, bank: a.bank_name, makeDefault: false } : undefined);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!a || !values) return;
    const patch: UpdateBankAccountInput = {};
    if (values.holder.trim() !== a.account_holder_name) patch.account_holder_name = values.holder.trim();
    if (values.bank.trim() !== a.bank_name) patch.bank_name = values.bank.trim();
    if (values.makeDefault && !a.is_default) patch.is_default = true;
    if (!Object.keys(patch).length) return onClose();
    setBusy(true);
    setErrors({});
    setFormError(undefined);
    try {
      await api.updateBankAccount(id, patch);
      toast.success("Bank account updated.");
      onSaved();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) setErrors(err.fieldMap);
      else setFormError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Edit bank account"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>Cancel</Button>
          <Button variant="primary" type="submit" form="edit-account" loading={busy} disabled={!a}>Save changes</Button>
        </>
      }
    >
      {account.error && !a ? <ErrorState error={account.error} onRetry={() => void account.reload()} /> : !a || !values ? <Spinner /> : (
        <form id="edit-account" className="form" onSubmit={submit}>
          <p className="muted small">The account number and IFSC cannot change. To use different ones, add a new account.</p>
          <div className="grid-2">
            <Field label="Account number">{(fid) => <input id={fid} disabled value={`•••• •••• ${a.account_number_last_four}`} />}</Field>
            <Field label="IFSC">{(fid) => <input id={fid} disabled value={a.ifsc} />}</Field>
          </div>
          <Field label="Account holder name" error={errors.account_holder_name}>
            {(fid) => <input id={fid} required maxLength={150} value={values.holder} onChange={(e) => setDraft({ ...values, holder: e.target.value })} />}
          </Field>
          <Field label="Bank name" error={errors.bank_name}>
            {(fid) => <input id={fid} required maxLength={150} value={values.bank} onChange={(e) => setDraft({ ...values, bank: e.target.value })} />}
          </Field>
          {a.is_default ? (
            <p className="muted small">This is your default account. Make another account the default to change it.</p>
          ) : (
            <label className="check">
              <input type="checkbox" checked={values.makeDefault} onChange={(e) => setDraft({ ...values, makeDefault: e.target.checked })} />
              Make this my default account
            </label>
          )}
          {errors.is_default && <Alert tone="bad">{errors.is_default}</Alert>}
          {formError && <Alert tone="bad">{formError}</Alert>}
        </form>
      )}
    </Modal>
  );
}

export default function BankAccounts() {
  const accounts = useFetch((s) => api.listBankAccounts(s));
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string>();
  const [removing, setRemoving] = useState<BankAccount>();

  async function makeDefault(a: BankAccount) {
    try {
      await api.updateBankAccount(a.id, { is_default: true });
      toast.success(`${a.bank_name} ••${a.account_number_last_four} is now your default account.`);
      void accounts.reload(true);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  return (
    <>
      <PageHeader
        title="Bank accounts"
        subtitle="Accounts you can settle and pay out to."
        actions={<Button variant="primary" icon="plus" onClick={() => setAdding(true)}>Add bank account</Button>}
      />

      {accounts.error && !accounts.data ? (
        <Card><ErrorState error={accounts.error} onRetry={() => void accounts.reload()} /></Card>
      ) : !accounts.data ? (
        <Spinner />
      ) : accounts.data.length === 0 ? (
        <Card><EmptyState icon="bank" title="No bank accounts yet" action={<Button variant="primary" icon="plus" onClick={() => setAdding(true)}>Add your first account</Button>}>Add an account to receive settlements and payouts.</EmptyState></Card>
      ) : (
        <div className="grid-cards">
          {accounts.data.map((a) => (
            <div key={a.id} className={`bank-card ${a.is_default ? "bank-card-default" : ""}`}>
              <div className="bank-card-top">
                <span className="bank-icon"><Icon name="bank" size={20} /></span>
                {a.is_default && <span className="badge badge-good">Default</span>}
              </div>
              <h3>{a.bank_name}</h3>
              <p className="bank-number">•••• •••• {a.account_number_last_four}</p>
              <dl className="bank-meta">
                <div><dt>Holder</dt><dd>{a.account_holder_name}</dd></div>
                <div><dt>IFSC</dt><dd className="mono">{a.ifsc}</dd></div>
                <div><dt>Type</dt><dd>{a.account_type === "SAVINGS" ? "Savings" : "Current"}</dd></div>
                <div><dt>Added</dt><dd>{formatDate(a.created_at)}</dd></div>
              </dl>
              <div className="bank-actions">
                {!a.is_default && <Button size="sm" onClick={() => void makeDefault(a)}>Make default</Button>}
                <Button size="sm" icon="edit" onClick={() => setEditing(a.id)}>Edit</Button>
                <Button size="sm" variant="ghost" icon="trash" onClick={() => setRemoving(a)}>Remove</Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {adding && <AddModal first={!accounts.data?.length} onClose={() => setAdding(false)} onAdded={() => void accounts.reload(true)} />}
      {editing && <EditModal id={editing} onClose={() => setEditing(undefined)} onSaved={() => void accounts.reload(true)} />}
      {removing && (
        <ConfirmDialog
          title="Remove bank account"
          confirmLabel="Remove account"
          danger
          onClose={() => setRemoving(undefined)}
          onConfirm={async () => {
            await api.removeBankAccount(removing.id);
            toast.success("Bank account removed.");
            await accounts.reload(true);
          }}
        >
          <p>Remove <strong>{removing.bank_name} ••{removing.account_number_last_four}</strong>? You will not be able to settle or pay out to it. Past payouts keep a record of where they went.</p>
        </ConfirmDialog>
      )}
    </>
  );
}
