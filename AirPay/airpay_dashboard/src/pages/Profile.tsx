import { useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "../api/client";
import * as api from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { Alert, Button, Card, Field, KeyValue, PageHeader, useToast } from "../components/ui";
import { formatDate } from "../lib/format";

const FIELDS = ["first_name", "last_name", "company_name", "company_address"] as const;

export default function Profile() {
  const { customer, setCustomer, signOut } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState(() => ({
    first_name: customer?.first_name ?? "",
    last_name: customer?.last_name ?? "",
    company_name: customer?.company_name ?? "",
    company_address: customer?.company_address ?? "",
  }));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string>();
  const [busy, setBusy] = useState(false);

  if (!customer) return null;
  const dirty = FIELDS.some((f) => form[f].trim() !== customer[f]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setFormError(undefined);
    try {
      const patch = Object.fromEntries(FIELDS.map((f) => [f, form[f].trim()]));
      const updated = await api.updateMe(patch);
      setCustomer(updated);
      toast.success("Profile updated.");
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) setErrors(err.fieldMap);
      else setFormError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Profile" subtitle="Your account and business details." />
      <div className="grid-2-1">
        <Card title="Business details">
          <form className="form" onSubmit={submit}>
            <div className="grid-2">
              <Field label="First name" error={errors.first_name}>
                {(id) => <input id={id} required maxLength={150} value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />}
              </Field>
              <Field label="Last name" error={errors.last_name}>
                {(id) => <input id={id} required maxLength={150} value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />}
              </Field>
            </div>
            <Field label="Company name" error={errors.company_name}>
              {(id) => <input id={id} required maxLength={150} value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} />}
            </Field>
            <Field label="Company address" error={errors.company_address}>
              {(id) => <textarea id={id} required rows={3} maxLength={500} value={form.company_address} onChange={(e) => setForm({ ...form, company_address: e.target.value })} />}
            </Field>
            {formError && <Alert tone="bad">{formError}</Alert>}
            <div className="row-end">
              <Button type="submit" variant="primary" loading={busy} disabled={!dirty}>Save changes</Button>
            </div>
          </form>
        </Card>

        <div className="stack">
          <Card title="Account">
            <KeyValue
              rows={[
                ["Email", customer.email],
                ["Customer ID", <span className="mono small">{customer.id}</span>],
                ["Member since", formatDate(customer.date_joined)],
              ]}
            />
            <p className="muted small">Your email is your login, so it cannot be changed here.</p>
          </Card>
          <Card title="Session">
            <p className="muted small">Logging out revokes your refresh token on the server. The access token on this device is discarded.</p>
            <Button variant="danger" icon="logout" onClick={() => void signOut()}>Log out</Button>
          </Card>
        </div>
      </div>
    </>
  );
}
