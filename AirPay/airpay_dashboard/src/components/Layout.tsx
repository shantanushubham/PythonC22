import { Suspense, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { getHealth } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { Icon, Spinner, type IconName } from "./ui";

const NAV: { to: string; label: string; icon: IconName; end?: boolean }[] = [
  { to: "/", label: "Dashboard", icon: "home", end: true },
  { to: "/transactions", label: "Transactions", icon: "list" },
  { to: "/collect", label: "Collect payment", icon: "card" },
  { to: "/refunds", label: "Refunds", icon: "undo" },
  { to: "/balance", label: "Balance & settlements", icon: "wallet" },
  { to: "/payouts", label: "Payouts", icon: "send" },
  { to: "/bank-accounts", label: "Bank accounts", icon: "bank" },
  { to: "/api-keys", label: "API keys", icon: "key" },
  { to: "/profile", label: "Profile", icon: "user" },
];

export function Logo() {
  return (
    <span className="logo">
      <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">
        <defs>
          <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#6366f1" />
            <stop offset="1" stopColor="#8b5cf6" />
          </linearGradient>
        </defs>
        <rect width="32" height="32" rx="8" fill="url(#lg)" />
        <path d="M8 21 16 9l8 12h-4.5L16 15.5 12.5 21z" fill="#fff" />
      </svg>
      <span>AirPay</span>
    </span>
  );
}

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("airpay.theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("airpay.theme", theme);
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))] as const;
}

function GatewayStatus() {
  const [state, setState] = useState<"checking" | "ok" | "down">("checking");
  useEffect(() => {
    let alive = true;
    const check = () =>
      getHealth()
        .then(() => alive && setState("ok"))
        .catch(() => alive && setState("down"));
    void check();
    const timer = setInterval(check, 30_000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);
  const label = { checking: "Checking gateway…", ok: "Gateway online", down: "Gateway unreachable" }[state];
  return (
    <span className={`gateway gateway-${state}`} title="GET /api/v1/health">
      <span className="dot" />
      {label}
    </span>
  );
}

export function Layout() {
  const { customer, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [theme, toggleTheme] = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => setOpen(false), [location.pathname]);

  const initials = `${customer?.first_name?.[0] ?? ""}${customer?.last_name?.[0] ?? ""}`.toUpperCase() || "?";

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="sidebar-top">
          <Logo />
        </div>
        <nav className="nav" aria-label="Main">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              <Icon name={item.icon} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <GatewayStatus />
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}

      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Open menu">
            <Icon name="menu" />
          </button>
          <div className="topbar-title">
            <strong>{customer?.company_name}</strong>
          </div>
          <div className="topbar-right">
            <button className="icon-btn" onClick={toggleTheme} aria-label="Toggle dark mode" title="Toggle dark mode">
              <Icon name={theme === "dark" ? "sun" : "moon"} />
            </button>
            <button className="user-chip" onClick={() => navigate("/profile")}>
              <span className="avatar">{initials}</span>
              <span className="user-chip-text">
                <span>
                  {customer?.first_name} {customer?.last_name}
                </span>
                <small className="muted">{customer?.email}</small>
              </span>
            </button>
            <button className="icon-btn" onClick={() => void signOut()} aria-label="Log out" title="Log out">
              <Icon name="logout" />
            </button>
          </div>
        </header>
        <main className="content">
          <Suspense fallback={<Spinner />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
