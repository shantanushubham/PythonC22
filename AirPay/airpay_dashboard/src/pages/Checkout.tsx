import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import * as api from "../api/endpoints";
import type { CreateTransactionInput, Method, Transaction, WhoAmI } from "../api/types";
import { Alert, Button, Card, CopyButton, EmptyState, Field, Icon, KeyValue, MethodBadge, PageHeader, StatusBadge, useToast } from "../components/ui";
import { BANKS, METHODS, METHOD_LABEL, TEST_CARDS, TEST_NETBANKING_LOGINS, TEST_VPAS } from "../lib/constants";
import { checkoutKey, useCheckoutKey } from "../lib/checkoutKey";
import { formatDate, formatDateTime, formatMoney, newKey } from "../lib/format";
import { instrumentLabel } from "../lib/txn";

const FINAL = new Set(["SUCCESS", "FAILED", "EXPIRED", "CANCELLED"]);

// --- Step 1: the API key ------------------------------------------------------------------

function KeyPanel() {
  const stored = useCheckoutKey();
  const toast = useToast();
  const [input, setInput] = useState("");
  const [who, setWho] = useState<WhoAmI>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState<"verify" | "create" | undefined>();

  const verify = useCallback(async (key: string) => {
    setBusy("verify");
    setError(undefined);
    try {
      setWho(await api.paymentWhoAmI(key));
      return true;
    } catch (e) {
      setWho(undefined);
      setError(e instanceof ApiError && e.status === 401 ? "That API key is not valid. It may be revoked or expired." : errorMessage(e));
      return false;
    } finally {
      setBusy(undefined);
    }
  }, []);

  // Check a key that is already stored in this tab.
  useEffect(() => {
    if (stored) void verify(stored);
    else setWho(undefined);
  }, [stored, verify]);

  async function save() {
    const key = input.trim();
    if (!key) return;
    if (await verify(key)) {
      checkoutKey.set(key);
      setInput("");
      toast.success("API key saved for this tab.");
    }
  }

  async function createTestKey() {
    setBusy("create");
    setError(undefined);
    try {
      const expires = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
      const created = await api.createApiKey({ name: "Dashboard checkout (test)", expires_at: expires });
      checkoutKey.set(created.key);
      toast.success("Created a test key that expires in 24 hours.");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(undefined);
    }
  }

  return (
    <Card
      title={<><Icon name="key" size={18} /> Step 1 · API key</>}
      actions={stored ? <Button size="sm" onClick={() => checkoutKey.set("")}>Forget key</Button> : undefined}
    >
      <p className="muted small">
        Payments are created with an <strong>API key</strong>, not your login. The key is kept only in this browser tab.
      </p>
      {stored ? (
        who ? (
          <div className="key-ok">
            <Icon name="shield" size={20} />
            <div>
              <strong>{who.api_key_prefix}…</strong> verified for {who.company_name}
              <small className="muted block">Expires {formatDate(who.api_key_expires_at)} · calls GET /payments/whoami</small>
            </div>
          </div>
        ) : error ? (
          <Alert tone="bad">{error}</Alert>
        ) : (
          <p className="muted">Verifying key…</p>
        )
      ) : (
        <div className="stack">
          <div className="inline-form">
            <input
              aria-label="API key"
              placeholder="Paste an API key (apk_…)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void save()}
              autoComplete="off"
              spellCheck={false}
            />
            <Button onClick={() => void save()} loading={busy === "verify"} disabled={!input.trim()}>Use key</Button>
          </div>
          <div className="or"><span>or</span></div>
          <Button variant="primary" icon="plus" loading={busy === "create"} onClick={() => void createTestKey()}>
            Create a test key for me (24 hours)
          </Button>
          {error && <Alert tone="bad">{error}</Alert>}
          <p className="muted small">
            Secrets are shown only once when a key is created. Manage keys on the <Link to="/api-keys">API keys</Link> page.
          </p>
        </div>
      )}
    </Card>
  );
}

// --- Step 2: the payment form -------------------------------------------------------------

interface FormState {
  method: Method;
  amount: string;
  reference: string;
  description: string;
  card_type: "credit" | "debit";
  number: string;
  expiry_month: string;
  expiry_year: string;
  cvv: string;
  holder_name: string;
  payer_vpa: string;
  bank_code: string;
}

const INITIAL: FormState = {
  method: "CARD",
  amount: "",
  reference: "",
  description: "",
  card_type: "credit",
  number: "",
  expiry_month: "12",
  expiry_year: String(new Date().getFullYear() + 4),
  cvv: "",
  holder_name: "",
  payer_vpa: "",
  bank_code: "HDFC",
};

const groupCard = (v: string) => v.replace(/\D/g, "").slice(0, 19).replace(/(.{4})/g, "$1 ").trim();

function buildBody(f: FormState): CreateTransactionInput {
  const body: CreateTransactionInput = { method: f.method, amount: f.amount.trim() };
  if (f.reference.trim()) body.reference = f.reference.trim();
  if (f.description.trim() && f.method === "UPI") body.description = f.description.trim();
  if (f.method === "CARD") {
    body.card = {
      card_type: f.card_type,
      number: f.number.replace(/\s/g, ""),
      expiry_month: Number(f.expiry_month),
      expiry_year: Number(f.expiry_year),
      cvv: f.cvv,
      holder_name: f.holder_name.trim(),
    };
  } else if (f.method === "UPI") {
    body.payer_vpa = f.payer_vpa.trim();
  } else {
    body.bank_code = f.bank_code;
    // The bank sends the customer back here. /pay/return then confirms the outcome with the gateway.
    body.return_url = `${window.location.origin}/pay/return`;
  }
  return body;
}

function PaymentForm({ apiKey, onCreated }: { apiKey: string; onCreated: (t: Transaction) => void }) {
  const [form, setForm] = useState<FormState>(INITIAL);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string>();
  const [busy, setBusy] = useState(false);
  // Same body => same Idempotency-Key, so a retry after a network error cannot charge twice.
  const attempt = useRef<{ signature: string; key: string }>({ signature: "", key: "" });

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }));
  const text = (key: keyof FormState) => (e: { target: { value: string } }) => set(key, e.target.value as never);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErrors({});
    setFormError(undefined);
    setBusy(true);
    const body = buildBody(form);
    const signature = JSON.stringify(body);
    if (attempt.current.signature !== signature) attempt.current = { signature, key: newKey() };
    try {
      const txn = await api.createTransaction(apiKey, body, attempt.current.key);
      attempt.current = { signature: "", key: "" };
      onCreated(txn);
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) {
        setErrors(err.fieldMap);
        const known = ["amount", "reference", "description", "payer_vpa", "bank_code", "return_url", "card.card_type", "card.number", "card.expiry_month", "card.expiry_year", "card.cvv", "card.holder_name", "card"];
        const other = err.errors.filter((x) => !known.includes(x.field));
        if (other.length) setFormError(other.map((x) => x.message).join(" · "));
      } else if (err instanceof ApiError && err.status === 401) {
        setFormError("The API key was rejected. Forget it and add a valid key.");
      } else if (err instanceof ApiError && err.status === 503) {
        setFormError(`${err.message}. The payment service did not answer. Check that it is running and try again.`);
      } else if (err instanceof ApiError && err.status === 409) {
        attempt.current = { signature: "", key: "" };
        setFormError(err.message);
      } else {
        setFormError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  }

  const bank = BANKS.find((b) => b.code === form.bank_code);
  const years = Array.from({ length: 16 }, (_, i) => new Date().getFullYear() + i);

  return (
    <Card title={<><Icon name="card" size={18} /> Step 2 · Take a payment</>}>
      <div className="tabs" role="tablist">
        {METHODS.map((m) => (
          <button key={m} role="tab" type="button" aria-selected={form.method === m} className={`tab ${form.method === m ? "tab-on" : ""}`} onClick={() => { set("method", m); setErrors({}); setFormError(undefined); }}>
            {METHOD_LABEL[m]}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="form" noValidate>
        <div className="grid-2">
          <Field label="Amount (₹)" error={errors.amount} hint={form.method === "UPI" ? "UPI minimum is ₹1.00" : undefined}>
            {(id) => <input id={id} inputMode="decimal" placeholder="1500.00" value={form.amount} onChange={text("amount")} />}
          </Field>
          <Field label="Your reference (optional)" error={errors.reference} hint="Letters, digits, _ and - · up to 64">
            {(id) => <input id={id} maxLength={64} placeholder="order_1001" value={form.reference} onChange={text("reference")} />}
          </Field>
        </div>

        {form.method === "CARD" && (
          <>
            <Field label="Test card" hint="Fills in a card that gives a known result on the mock card network.">
              {(id) => (
                <select
                  id={id}
                  value=""
                  onChange={(e) => {
                    const c = TEST_CARDS[Number(e.target.value)];
                    if (!c) return;
                    setForm((f) => ({ ...f, number: groupCard(c.number), cvv: c.cvv, card_type: c.type, holder_name: f.holder_name || "Jane Doe" }));
                  }}
                >
                  <option value="">Choose a test card…</option>
                  {TEST_CARDS.map((c, i) => <option key={c.label + i} value={i}>{c.label} · {c.number.slice(-4)}</option>)}
                </select>
              )}
            </Field>
            <div className="grid-2">
              <Field label="Card number" error={errors["card.number"]}>
                {(id) => <input id={id} inputMode="numeric" autoComplete="off" placeholder="4111 1111 1111 1111" value={form.number} onChange={(e) => set("number", groupCard(e.target.value))} />}
              </Field>
              <Field label="Name on card" error={errors["card.holder_name"]}>
                {(id) => <input id={id} autoComplete="off" placeholder="Jane Doe" value={form.holder_name} onChange={text("holder_name")} />}
              </Field>
            </div>
            <div className="grid-4-form">
              <Field label="Type" error={errors["card.card_type"]}>
                {(id) => (
                  <select id={id} value={form.card_type} onChange={text("card_type")}>
                    <option value="credit">Credit</option>
                    <option value="debit">Debit</option>
                  </select>
                )}
              </Field>
              <Field label="Month" error={errors["card.expiry_month"]}>
                {(id) => (
                  <select id={id} value={form.expiry_month} onChange={text("expiry_month")}>
                    {Array.from({ length: 12 }, (_, i) => <option key={i} value={i + 1}>{String(i + 1).padStart(2, "0")}</option>)}
                  </select>
                )}
              </Field>
              <Field label="Year" error={errors["card.expiry_year"]}>
                {(id) => (
                  <select id={id} value={form.expiry_year} onChange={text("expiry_year")}>
                    {years.map((y) => <option key={y} value={y}>{y}</option>)}
                  </select>
                )}
              </Field>
              <Field label="CVV" error={errors["card.cvv"]}>
                {(id) => <input id={id} inputMode="numeric" maxLength={4} autoComplete="off" placeholder="123" value={form.cvv} onChange={(e) => set("cvv", e.target.value.replace(/\D/g, ""))} />}
              </Field>
            </div>
            {errors.card && <Alert tone="bad">{errors.card}</Alert>}
            <p className="muted small">The card number and CVV go to the card service only. AirPay never stores them.</p>
          </>
        )}

        {form.method === "UPI" && (
          <>
            <Field label="Payer UPI ID" error={errors.payer_vpa} hint="The payer approves a collect request in their UPI app.">
              {(id) => <input id={id} placeholder="jane.doe@okaxis" autoComplete="off" value={form.payer_vpa} onChange={text("payer_vpa")} />}
            </Field>
            <div className="chips">
              {TEST_VPAS.map((v) => (
                <button type="button" key={v.vpa} className="chip" onClick={() => set("payer_vpa", v.vpa)} title={v.vpa}>{v.label}</button>
              ))}
            </div>
            <Field label="Note to payer (optional)" error={errors.description} hint="Up to 50 characters">
              {(id) => <input id={id} maxLength={50} value={form.description} onChange={text("description")} />}
            </Field>
          </>
        )}

        {form.method === "NETBANKING" && (
          <>
            <Field label="Bank" error={errors.bank_code}>
              {(id) => (
                <select id={id} value={form.bank_code} onChange={text("bank_code")}>
                  {BANKS.map((b) => <option key={b.code} value={b.code}>{b.name} ({b.code}){b.down ? " · currently down" : ""}</option>)}
                </select>
              )}
            </Field>
            {bank?.down && <Alert tone="warn">The mock bank list reports {bank.name} as down, so the gateway will answer 503.</Alert>}
            {errors.return_url && <Alert tone="bad">{errors.return_url}</Alert>}
            <Alert tone="info">
              You will be sent to the bank's login page, then back here. {TEST_NETBANKING_LOGINS}
            </Alert>
          </>
        )}

        {formError && <Alert tone="bad">{formError}</Alert>}
        <Button type="submit" variant="primary" loading={busy} className="btn-block">
          {form.method === "NETBANKING" ? "Continue to bank" : form.method === "UPI" ? "Send collect request" : "Pay"}
          {form.amount.trim() && !errors.amount ? ` · ${formatMoney(form.amount.trim())}` : ""}
        </Button>
      </form>
    </Card>
  );
}

// --- Result -------------------------------------------------------------------------------

function Result({ txn: initial, apiKey, onDone }: { txn: Transaction; apiKey: string; onDone: () => void }) {
  const [txn, setTxn] = useState(initial);

  // UPI starts PENDING. GET /transactions/{id} with the same API key asks the rail again.
  useEffect(() => {
    if (FINAL.has(txn.status) || txn.method === "NETBANKING") return;
    const controller = new AbortController();
    const timer = setInterval(async () => {
      try {
        const next = await api.getTransactionWithKey(apiKey, txn.id, controller.signal);
        setTxn(next);
      } catch {
        /* keep polling */
      }
    }, 2000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [apiKey, txn.id, txn.status, txn.method]);

  const done = FINAL.has(txn.status);
  const tone = txn.status === "SUCCESS" ? "good" : done ? "bad" : "pending";

  return (
    <Card>
      <div className={`result result-${tone}`}>
        <div className="result-icon">
          {tone === "pending" ? <span className="spinner" /> : <Icon name={tone === "good" ? "check" : "x"} size={30} />}
        </div>
        <h2>
          {txn.status === "SUCCESS" && "Payment successful"}
          {txn.status === "FAILED" && "Payment failed"}
          {txn.status === "EXPIRED" && "Payment expired"}
          {txn.status === "CANCELLED" && "Payment cancelled"}
          {txn.status === "PENDING" && (txn.method === "NETBANKING" ? "Waiting for the bank" : "Waiting for the payer to approve")}
        </h2>
        <p className="result-amount">{formatMoney(txn.amount)}</p>
        {txn.failure_reason && <p className="muted">{txn.failure_reason}{txn.failure_code && <> · <code>{txn.failure_code}</code></>}</p>}
        {txn.status === "SUCCESS" && <p className="muted">You receive {formatMoney(txn.net_amount)} after {formatMoney(txn.commission)} commission ({txn.commission_rate}%).</p>}
      </div>

      <KeyValue
        rows={[
          ["Transaction ID", <span className="inline"><span className="mono">{txn.id}</span><CopyButton value={txn.id} /></span>],
          ["Method", <MethodBadge method={txn.method} />],
          ["Payer", instrumentLabel(txn)],
          ["Status", <StatusBadge status={txn.status} />],
          ["Reference", txn.reference || "—"],
        ]}
      />

      <div className="result-actions">
        {txn.status === "PENDING" && txn.method === "NETBANKING" && txn.redirect_url && (
          <Button variant="primary" icon="external" onClick={() => { window.location.href = txn.redirect_url; }}>
            Continue to the bank
          </Button>
        )}
        <Link to={`/transactions/${txn.id}`} className="btn btn-secondary btn-md">View details</Link>
        <Button onClick={onDone} icon="plus">New payment</Button>
      </div>
    </Card>
  );
}

// --- Recent payments made with the key ----------------------------------------------------

function RecentWithKey({ apiKey, refreshToken }: { apiKey: string; refreshToken: number }) {
  const [items, setItems] = useState<Transaction[]>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let alive = true;
    api
      .listTransactionsWithKey(apiKey)
      .then((r) => alive && (setItems(r.slice(0, 5)), setError(undefined)))
      .catch((e) => alive && setError(errorMessage(e)));
    return () => {
      alive = false;
    };
  }, [apiKey, refreshToken]);

  return (
    <Card title="Recent payments through this key" pad={false} actions={<span className="muted small">GET /transactions</span>}>
      {error ? (
        <div className="card-body"><Alert tone="bad">{error}</Alert></div>
      ) : !items ? (
        <div className="card-body muted">Loading…</div>
      ) : items.length === 0 ? (
        <EmptyState title="No payments yet">Payments you take above show up here.</EmptyState>
      ) : (
        <ul className="feed">
          {items.map((t) => (
            <li key={t.id}>
              <div>
                <Link to={`/transactions/${t.id}`}><strong>{formatMoney(t.amount)}</strong></Link> <span className="muted">{instrumentLabel(t)}</span>
                <small className="muted block">{formatDateTime(t.created_at)}</small>
              </div>
              <StatusBadge status={t.status} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function Checkout() {
  const apiKey = useCheckoutKey();
  const [result, setResult] = useState<Transaction>();
  const [bump, setBump] = useState(0);

  return (
    <>
      <PageHeader title="Collect a payment" subtitle="Try the payment API the way your own app would: with an API key, over card, UPI or netbanking." />
      <div className="grid-checkout">
        <div className="stack">
          <KeyPanel />
          {apiKey && !result && <PaymentForm apiKey={apiKey} onCreated={(t) => { setResult(t); setBump((n) => n + 1); }} />}
          {apiKey && result && <Result key={result.id} txn={result} apiKey={apiKey} onDone={() => setResult(undefined)} />}
        </div>
        <div className="stack">{apiKey ? <RecentWithKey apiKey={apiKey} refreshToken={bump} /> : (
          <Card><EmptyState icon="key" title="Add an API key first">Once a key is set, you can take payments and see them here.</EmptyState></Card>
        )}</div>
      </div>
    </>
  );
}
