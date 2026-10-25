import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { errorMessage } from "../api/client";
import type { Method, RefundState, TxnStatus } from "../api/types";
import { METHOD_LABEL } from "../lib/constants";
import { titleCase } from "../lib/format";

// --- Icons (feather-style strokes) --------------------------------------------------------

const ICONS = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  card: "M2 6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2zM2 10h20",
  wallet: "M3 7a2 2 0 0 1 2-2h13v4M3 7v11a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-9a1 1 0 0 0-1-1H5a2 2 0 0 1-2-2zM16 14.5h.01",
  send: "m22 2-7 20-4-9-9-4zM22 2 11 13",
  bank: "M3 21h18M5 21V10M9 21V10M15 21V10M19 21V10M2 10l10-7 10 7z",
  key: "M21 2l-2 2m-7.6 7.6a5.5 5.5 0 1 1-7.8 7.8 5.5 5.5 0 0 1 7.8-7.8zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4",
  user: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  plus: "M12 5v14M5 12h14",
  check: "M20 6 9 17l-5-5",
  x: "M18 6 6 18M6 6l12 12",
  copy: "M9 9h11v11H9zM5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1",
  trash: "M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m3 0-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6",
  edit: "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
  refresh: "M23 4v6h-6M1 20v-6h6M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  arrowRight: "M5 12h14M12 5l7 7-7 7",
  arrowLeft: "M19 12H5M12 19l-7-7 7-7",
  alert: "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01",
  info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 16v-4M12 8h.01",
  menu: "M3 6h18M3 12h18M3 18h18",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
  external: "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3",
  phone: "M7 2h10a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zM12 18h.01",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  eye: "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  undo: "M1 4v6h6M3.5 15a9 9 0 1 0 2.1-9.4L1 10",
  trend: "M23 6l-9.5 9.5-5-5L1 18M17 6h6v6",
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="icon"
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

// --- Buttons ------------------------------------------------------------------------------

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
  icon?: IconName;
}

export function Button({ variant = "secondary", size = "md", loading, icon, children, disabled, className = "", ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      className={`btn btn-${variant} btn-${size} ${className}`}
    >
      {loading ? <span className="spinner spinner-sm" /> : icon ? <Icon name={icon} size={size === "sm" ? 15 : 17} /> : null}
      {children}
    </button>
  );
}

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      size="sm"
      icon={copied ? "check" : "copy"}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
        } catch {
          // Clipboard is blocked on plain http outside localhost. Fall back to a hidden textarea.
          const area = document.createElement("textarea");
          area.value = value;
          document.body.appendChild(area);
          area.select();
          document.execCommand("copy");
          area.remove();
        }
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "Copied" : label}
    </Button>
  );
}

// --- Layout pieces ------------------------------------------------------------------------

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Card({ title, actions, children, className = "", pad = true }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-header">
          <h2>{title}</h2>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      <div className={pad ? "card-body" : ""}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "good" | "warn" | "bad" }) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ""}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="center-block" role="status">
      <span className="spinner" />
      {label && <span className="muted">{label}</span>}
    </div>
  );
}

export function EmptyState({ icon = "list", title, children, action }: { icon?: IconName; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon name={icon} size={26} />
      </div>
      <h3>{title}</h3>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="empty">
      <div className="empty-icon empty-icon-bad">
        <Icon name="alert" size={26} />
      </div>
      <h3>Could not load this</h3>
      <p className="muted">{errorMessage(error)}</p>
      {onRetry && (
        <Button icon="refresh" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function Alert({ tone = "info", children, onClose }: { tone?: "info" | "warn" | "bad" | "good"; children: ReactNode; onClose?: () => void }) {
  return (
    <div className={`alert alert-${tone}`} role={tone === "bad" ? "alert" : "status"}>
      <Icon name={tone === "good" ? "check" : tone === "info" ? "info" : "alert"} size={18} />
      <div className="alert-body">{children}</div>
      {onClose && (
        <button className="icon-btn" onClick={onClose} aria-label="Dismiss">
          <Icon name="x" size={16} />
        </button>
      )}
    </div>
  );
}

// --- Badges -------------------------------------------------------------------------------

const STATUS_TONE: Record<string, string> = {
  SUCCESS: "good",
  PENDING: "warn",
  FAILED: "bad",
  EXPIRED: "muted",
  CANCELLED: "muted",
  active: "good",
  revoked: "bad",
  expired: "muted",
};

export function StatusBadge({ status }: { status: TxnStatus | string }) {
  return (
    <span className={`badge badge-${STATUS_TONE[status] ?? "muted"}`}>
      {status === "PENDING" && <span className="pulse" />}
      {titleCase(status)}
    </span>
  );
}

/** Shown beside a payment's status once part or all of it has been refunded. */
export function RefundBadge({ state }: { state: RefundState }) {
  if (state === "NONE") return null;
  return <span className={`badge ${state === "FULL" ? "badge-muted" : "badge-warn"}`}>{state === "FULL" ? "Refunded" : "Partly refunded"}</span>;
}

const METHOD_ICON: Record<Method, IconName> = { CARD: "card", UPI: "phone", NETBANKING: "bank" };

export function MethodBadge({ method }: { method: Method }) {
  return (
    <span className="method">
      <Icon name={METHOD_ICON[method]} size={15} />
      {METHOD_LABEL[method]}
    </span>
  );
}

// --- Forms --------------------------------------------------------------------------------

export function Field({ label, error, hint, children }: { label: string; error?: string; hint?: ReactNode; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className={`field ${error ? "field-error" : ""}`}>
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {error ? <span className="field-msg">{error}</span> : hint ? <span className="field-hint">{hint}</span> : null}
    </div>
  );
}

// --- Modal --------------------------------------------------------------------------------

export function Modal({ title, onClose, children, footer, wide }: { title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  // Keep the latest onClose without re-running the effect (which would steal focus on every render).
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    ref.current?.querySelector<HTMLElement>("input, select, textarea, button.btn-primary")?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      previous?.focus();
    };
  }, []);

  return createPortal(
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "modal-wide" : ""}`} role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <header className="modal-header">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <Icon name="x" />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-footer">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}

export function ConfirmDialog({
  title,
  children,
  confirmLabel,
  danger,
  onConfirm,
  onClose,
}: {
  title: string;
  children: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            loading={busy}
            onClick={async () => {
              setBusy(true);
              setError(undefined);
              try {
                await onConfirm();
                onClose();
              } catch (e) {
                setError(errorMessage(e));
                setBusy(false);
              }
            }}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      {children}
      {error && <Alert tone="bad">{error}</Alert>}
    </Modal>
  );
}

// --- Toasts -------------------------------------------------------------------------------

interface Toast {
  id: number;
  tone: "good" | "bad" | "info";
  text: string;
}

const ToastContext = createContext<(tone: Toast["tone"], text: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const push = useCallback((tone: Toast["tone"], text: string) => {
    const id = next.current++;
    setToasts((t) => [...t, { id, tone, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            <Icon name={t.tone === "good" ? "check" : t.tone === "bad" ? "alert" : "info"} size={16} />
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const push = useContext(ToastContext);
  return useMemo(
    () => ({
      success: (text: string) => push("good", text),
      error: (text: string) => push("bad", text),
      info: (text: string) => push("info", text),
    }),
    [push],
  );
}

// --- Tables -------------------------------------------------------------------------------

export function Pager({ page, pages, onPage, total }: { page: number; pages: number; onPage: (p: number) => void; total: number }) {
  if (pages <= 1) return <div className="pager muted">{total} result{total === 1 ? "" : "s"}</div>;
  return (
    <div className="pager">
      <span className="muted">
        Page {page} of {pages} · {total} results
      </span>
      <div className="pager-buttons">
        <Button size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </Button>
        <Button size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}

export function KeyValue({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="kv">
      {rows.map(([k, v]) => (
        <div key={k} className="kv-row">
          <dt>{k}</dt>
          <dd>{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
