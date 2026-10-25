import { useSyncExternalStore } from "react";

// The API key used by the "Collect payment" page. API key secrets are shown once by the
// gateway, so the customer either pastes one or lets the page create a short-lived test key.
// It is kept in sessionStorage only: it disappears when the tab closes or the customer logs out.

const KEY = "airpay.checkoutKey";
const listeners = new Set<() => void>();

export const checkoutKey = {
  get: () => sessionStorage.getItem(KEY) ?? "",
  set(value: string) {
    if (value) sessionStorage.setItem(KEY, value);
    else sessionStorage.removeItem(KEY);
    listeners.forEach((l) => l());
  },
};

export function useCheckoutKey(): string {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    checkoutKey.get,
  );
}
