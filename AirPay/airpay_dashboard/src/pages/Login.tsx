import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, Button, Field } from "../components/ui";
import { AuthLayout } from "./AuthLayout";

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as { from?: string; registered?: string } | null;
  const [email, setEmail] = useState(state?.registered ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      await signIn(email.trim(), password);
      navigate(state?.from && state.from !== "/login" ? state.from : "/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError(`Too many attempts. Try again${err.retryAfter ? ` in ${err.retryAfter} seconds` : " in a minute"}.`);
      } else if (err instanceof ApiError && err.status === 401) {
        setError("The email or password is not correct.");
      } else {
        setError(err instanceof Error ? err.message : "Could not sign in.");
      }
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your AirPay merchant account."
      footer={<>New to AirPay? <Link to="/register">Create an account</Link></>}
    >
      {state?.registered && <Alert tone="good">Account created. Sign in to continue.</Alert>}
      <form onSubmit={submit} className="form">
        <Field label="Email">
          {(id) => <input id={id} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Field>
        <Field label="Password">
          {(id) => <input id={id} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        {error && <Alert tone="bad">{error}</Alert>}
        <Button type="submit" variant="primary" loading={busy} className="btn-block">
          Sign in
        </Button>
      </form>
    </AuthLayout>
  );
}
