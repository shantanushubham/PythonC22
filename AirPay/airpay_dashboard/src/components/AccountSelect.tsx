import type { BankAccount } from "../api/types";

export function accountLabel(a: Pick<BankAccount, "bank_name" | "account_number_last_four" | "account_holder_name">) {
  return `${a.bank_name} ••${a.account_number_last_four} · ${a.account_holder_name}`;
}

export function AccountSelect({ id, accounts, value, onChange }: { id: string; accounts: BankAccount[]; value: string; onChange: (id: string) => void }) {
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
      {accounts.map((a) => (
        <option key={a.id} value={a.id}>
          {accountLabel(a)}{a.is_default ? " (default)" : ""}
        </option>
      ))}
    </select>
  );
}

export function defaultAccountId(accounts: BankAccount[] | undefined): string {
  return accounts?.find((a) => a.is_default)?.id ?? accounts?.[0]?.id ?? "";
}
