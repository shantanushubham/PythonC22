import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { register } from "../api/endpoints";
import type { RegisterInput } from "../api/types";
import { Alert, Button, Field } from "../components/ui";
import { AuthLayout } from "./AuthLayout";

const FIELDS = ["first_name", "last_name", "email", "password", "company_name", "company_address"];

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState<RegisterInput>({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    company_name: "",
    company_address: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const set = (key: keyof RegisterInput) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setFormError(undefined);
    try {
      const email = form.email.trim();
      await register({ ...form, email });
      navigate("/login", { replace: true, state: { registered: email } });
    } catch (err) {
      if (err instanceof ApiError && err.errors.length) {
        setErrors(err.fieldMap);
        const other = err.describe(FIELDS);
        if (other !== err.message) setFormError(other);
      } else {
        setFormError(err instanceof Error ? err.message : "Could not create the account.");
      }
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Set up your business to start collecting payments."
      footer={<>Already registered? <Link to="/login">Sign in</Link></>}
    >
      <form onSubmit={submit} className="form">
        <div className="grid-2">
          <Field label="First name" error={errors.first_name}>
            {(id) => <input id={id} required maxLength={150} autoComplete="given-name" value={form.first_name} onChange={set("first_name")} />}
          </Field>
          <Field label="Last name" error={errors.last_name}>
            {(id) => <input id={id} required maxLength={150} autoComplete="family-name" value={form.last_name} onChange={set("last_name")} />}
          </Field>
        </div>
        <Field label="Work email" error={errors.email}>
          {(id) => <input id={id} type="email" required maxLength={150} autoComplete="email" value={form.email} onChange={set("email")} />}
        </Field>
        <Field label="Password" error={errors.password} hint="At least 8 characters. Not a common password, not all digits.">
          {(id) => <input id={id} type="password" required maxLength={128} autoComplete="new-password" value={form.password} onChange={set("password")} />}
        </Field>
        <Field label="Company name" error={errors.company_name}>
          {(id) => <input id={id} required maxLength={150} autoComplete="organization" value={form.company_name} onChange={set("company_name")} />}
        </Field>
        <Field label="Company address" error={errors.company_address}>
          {(id) => <textarea id={id} required rows={2} maxLength={500} value={form.company_address} onChange={set("company_address")} />}
        </Field>
        {formError && <Alert tone="bad">{formError}</Alert>}
        <Button type="submit" variant="primary" loading={busy} className="btn-block">
          Create account
        </Button>
      </form>
    </AuthLayout>
  );
}
