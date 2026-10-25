// Amounts from the gateway are strings such as "1500.50". Money maths is done in whole
// paise (integers), so 0.1 + 0.2 never turns into 0.30000000000000004.

export function toPaise(amount: string | null | undefined): number {
  if (!amount) return 0;
  const negative = amount.startsWith("-");
  const [whole, fraction = ""] = amount.replace("-", "").split(".");
  const paise = Number(whole || 0) * 100 + Number((fraction + "00").slice(0, 2));
  return negative ? -paise : paise;
}

export function fromPaise(paise: number): string {
  const sign = paise < 0 ? "-" : "";
  const abs = Math.abs(Math.round(paise));
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });
const inrCompact = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", notation: "compact", maximumFractionDigits: 1 });

export function formatMoney(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return "—";
  const paise = typeof amount === "number" ? Math.round(amount) : toPaise(amount);
  return inr.format(paise / 100);
}

export function formatMoneyCompact(paise: number): string {
  return inrCompact.format(paise / 100);
}

const dateTime = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
const dateOnly = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" });

const dateTimeShort = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

/** "25 Oct, 06:58 pm". Adds the year when it is not this year. */
export function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.getFullYear() === new Date().getFullYear() ? dateTimeShort.format(d) : dateTime.format(d);
}

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : "—";
}

export function formatDate(iso: string | null | undefined): string {
  return iso ? dateOnly.format(new Date(iso)) : "—";
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "never";
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 45) return "just now";
  if (seconds < 3600) return plural(Math.round(seconds / 60), "minute");
  if (seconds < 86400) return plural(Math.round(seconds / 3600), "hour");
  if (seconds < 86400 * 30) return plural(Math.round(seconds / 86400), "day");
  return formatDate(iso);
}

function plural(n: number, unit: string) {
  return `${n} ${unit}${n === 1 ? "" : "s"} ago`;
}

export function titleCase(text: string): string {
  return text.toLowerCase().replace(/(^|[\s_])\w/g, (m) => m.replace("_", " ").toUpperCase());
}

export function dayKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function newKey(): string {
  return crypto.randomUUID();
}

export function downloadCsv(filename: string, rows: (string | number)[][]) {
  const escape = (v: string | number) => {
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const blob = new Blob([rows.map((r) => r.map(escape).join(",")).join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
