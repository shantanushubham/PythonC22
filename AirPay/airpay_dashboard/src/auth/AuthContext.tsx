import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { onAuthLost, tokens } from "../api/client";
import * as api from "../api/endpoints";
import type { Customer } from "../api/types";

type Status = "loading" | "authed" | "anon";

interface AuthValue {
  status: Status;
  customer: Customer | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  setCustomer: (customer: Customer) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>(tokens.hasRefresh() ? "loading" : "anon");
  const [customer, setCustomer] = useState<Customer | null>(null);

  // Restore the session after a reload. `getMe` refreshes the access token if needed.
  useEffect(() => {
    if (!tokens.hasRefresh()) return;
    let cancelled = false;
    api
      .getMe()
      .then((me) => {
        if (cancelled) return;
        setCustomer(me);
        setStatus("authed");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("anon");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The refresh token was rejected somewhere in the app: go back to the login page.
  useEffect(
    () =>
      onAuthLost(() => {
        setCustomer(null);
        setStatus("anon");
      }),
    [],
  );

  const signIn = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    const me = await api.getMe();
    setCustomer(me);
    setStatus("authed");
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* the tokens are cleared either way */
    }
    sessionStorage.removeItem("airpay.checkoutKey");
    setCustomer(null);
    setStatus("anon");
  }, []);

  const value = useMemo(() => ({ status, customer, signIn, signOut, setCustomer }), [status, customer, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
