import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import * as api from "../api/endpoints";
import type { APIKey, CreatedAPIKey, WhoAmI } from "../api/types";
import { Alert, Button, Card, ConfirmDialog, CopyButton, EmptyState, ErrorState, Field, KeyValue, Modal, PageHeader, Spinner, StatusBadge, useToast } from "../components/ui";
import { checkoutKey } from "../lib/checkoutKey";
import { formatDate, formatDateTime, timeAgo } from "../lib/format";
import { useFetch } from "../lib/useFetch";

// Where your own app would call the gateway. The dashboard itself reaches it through the dev proxy.
const GATEWAY_URL = (import.meta.env.VITE_GATEWAY_URL as string | undefined) ?? "http://localhost:8000";

const PRESETS = [
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
  { label: "1 year", days: 365 },
];

function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (k: CreatedAPIKey) => void }) {
  const [name, setName] = useState("");
  const [days, setDays] = useState(90);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setFormError(undefined);
    try {
      // Expire a minute short of the limit so clock drift cannot push it past 365 days.
      const expires = new Date(Date.now() + days * 86_400_000 - 60_000).toISOString();
      onCreated(await api.createApiKey({ name: name.trim(), expires_at: expires }));
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) {
        setErrors(err.fieldMap);
        const other = err.errors.filter((x) => !["name", "expires_at"].includes(x.field));
        if (other.length) setFormError(other.map((x) => x.message).join(" · "));
      } else setFormError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Create an API key"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>Cancel</Button>
          <Button variant="primary" type="submit" form="create-key" loading={busy}>Create key</Button>
        </>
      }
    >
      <form id="create-key" className="form" onSubmit={submit}>
        <Field label="Name" error={errors.name} hint="So you can tell your keys apart, such as “Production” or “Staging”.">
          {(id) => <input id={id} maxLength={80} placeholder="Production" value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label="Expires in" error={errors.expires_at} hint="A key stops working when it expires. 365 days is the longest.">
          {(id) => (
            <select id={id} value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {PRESETS.map((p) => <option key={p.days} value={p.days}>{p.label}</option>)}
            </select>
          )}
        </Field>
        {formError && <Alert tone="bad">{formError}</Alert>}
      </form>
    </Modal>
  );
}

function SecretModal({ created, onClose }: { created: CreatedAPIKey; onClose: () => void }) {
  const toast = useToast();
  const [who, setWho] = useState<WhoAmI>();
  const [verifyError, setVerifyError] = useState<string>();
  const [checking, setChecking] = useState(false);

  async function verify() {
    setChecking(true);
    setVerifyError(undefined);
    try {
      setWho(await api.paymentWhoAmI(created.key));
    } catch (e) {
      setVerifyError(errorMessage(e));
    } finally {
      setChecking(false);
    }
  }

  return (
    <Modal title="Your new API key" onClose={onClose} footer={<Button variant="primary" onClick={onClose}>I have saved it</Button>}>
      <Alert tone="warn">Copy this key now. For your security it is shown <strong>only once</strong> and cannot be recovered. If you lose it, revoke it and create another.</Alert>
      <div className="secret">
        <code>{created.key}</code>
        <CopyButton value={created.key} />
      </div>
      <KeyValue rows={[["Name", created.name || "—"], ["Expires", formatDateTime(created.expires_at)]]} />
      <div className="inline wrap">
        <Button icon="shield" onClick={verify} loading={checking}>Verify key</Button>
        <Button
          onClick={() => {
            checkoutKey.set(created.key);
            toast.success("This key will be used on the Collect payment page.");
          }}
        >
          Use for test payments
        </Button>
      </div>
      {who && <Alert tone="good">Key works. It belongs to <strong>{who.company_name}</strong> ({who.email}).</Alert>}
      {verifyError && <Alert tone="bad">{verifyError}</Alert>}
      <p className="muted small">Send it as a header on payment requests:</p>
      <pre className="code">{`curl -X POST ${GATEWAY_URL}/api/v1/transactions \\
  -H "X-API-Key: ${created.key}" \\
  -H "Idempotency-Key: order-1001" \\
  -H "Content-Type: application/json" \\
  -d '{"method":"UPI","amount":"250.00","payer_vpa":"jane.doe@okaxis"}'`}</pre>
    </Modal>
  );
}

function KeyDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const key = useFetch(() => api.getApiKey(id), [id]);
  const k = key.data;
  return (
    <Modal title="API key details" onClose={onClose} footer={<Button onClick={onClose}>Close</Button>}>
      {key.error && !k ? <ErrorState error={key.error} onRetry={() => void key.reload()} /> : !k ? <Spinner /> : (
        <KeyValue
          rows={[
            ["Name", k.name || "—"],
            ["Key", <span className="mono">{k.prefix}…{k.last_four}</span>],
            ["Status", <StatusBadge status={k.status} />],
            ["Created", formatDateTime(k.created_at)],
            ["Expires", formatDateTime(k.expires_at)],
            ["Last used", k.last_used_at ? `${timeAgo(k.last_used_at)} (${formatDateTime(k.last_used_at)})` : "Never"],
            ["Revoked", k.revoked_at ? formatDateTime(k.revoked_at) : "—"],
          ]}
        />
      )}
    </Modal>
  );
}

export default function ApiKeys() {
  const keys = useFetch((s) => api.listApiKeys(s));
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<CreatedAPIKey>();
  const [detail, setDetail] = useState<string>();
  const [revoking, setRevoking] = useState<APIKey>();

  const active = (keys.data ?? []).filter((k) => k.status === "active").length;

  return (
    <>
      <PageHeader
        title="API keys"
        subtitle={<>Keys let your own app collect payments. <Link to="/collect">Try one on the Collect payment page.</Link></>}
        actions={<Button variant="primary" icon="plus" onClick={() => setCreating(true)}>Create API key</Button>}
      />

      <Alert tone="info">API keys can only create and read payments. They cannot change your account, settle funds or pay out — those need your login.</Alert>

      <Card title={`Your keys${keys.data ? ` · ${active} active` : ""}`} pad={false}>
        {keys.error && !keys.data ? (
          <ErrorState error={keys.error} onRetry={() => void keys.reload()} />
        ) : !keys.data ? (
          <Spinner />
        ) : keys.data.length === 0 ? (
          <EmptyState icon="key" title="No API keys yet" action={<Button variant="primary" icon="plus" onClick={() => setCreating(true)}>Create your first key</Button>}>
            Create a key to start taking payments from your app.
          </EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Key</th><th>Status</th><th>Expires</th><th>Last used</th><th /></tr></thead>
              <tbody>
                {keys.data.map((k) => (
                  <tr key={k.id}>
                    <td>
                      <span className="strong">{k.name || <span className="muted">Unnamed</span>}</span>
                      <small className="muted block mono">{k.prefix}…{k.last_four}</small>
                    </td>
                    <td><StatusBadge status={k.status} /></td>
                    <td className="nowrap">{formatDate(k.expires_at)}</td>
                    <td className="nowrap">{timeAgo(k.last_used_at)}</td>
                    <td className="row-actions">
                      <Button size="sm" onClick={() => setDetail(k.id)}>Details</Button>
                      {k.status === "active" && <Button size="sm" variant="ghost" icon="trash" onClick={() => setRevoking(k)} aria-label={`Revoke ${k.name || "key"}`} title="Revoke" />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {creating && (
        <CreateModal
          onClose={() => setCreating(false)}
          onCreated={(k) => {
            setCreating(false);
            setCreated(k);
            void keys.reload(true);
          }}
        />
      )}
      {created && <SecretModal created={created} onClose={() => setCreated(undefined)} />}
      {detail && <KeyDetail id={detail} onClose={() => setDetail(undefined)} />}
      {revoking && (
        <ConfirmDialog
          title="Revoke API key"
          confirmLabel="Revoke key"
          danger
          onClose={() => setRevoking(undefined)}
          onConfirm={async () => {
            await api.revokeApiKey(revoking.id);
            toast.success("API key revoked.");
            await keys.reload(true);
          }}
        >
          <p>Revoke <strong>{revoking.name || "this key"}</strong> (<span className="mono">{revoking.prefix}…{revoking.last_four}</span>)? Anything using it will stop working <strong>immediately</strong>. This cannot be undone.</p>
        </ConfirmDialog>
      )}
    </>
  );
}
