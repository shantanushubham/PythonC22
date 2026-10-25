import type { ReactNode } from "react";
import { Logo } from "../components/Layout";
import { Icon } from "../components/ui";

export function AuthLayout({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="auth">
      <div className="auth-brand">
        <Logo />
        <h2>Accept cards, UPI and netbanking. Keep track of every rupee.</h2>
        <ul>
          <li><Icon name="trend" /> Live dashboard of collections, commission and net earnings</li>
          <li><Icon name="wallet" /> Settle your balance and pay out to your bank</li>
          <li><Icon name="key" /> API keys to take payments from your own app</li>
        </ul>
      </div>
      <div className="auth-form">
        <div className="auth-card">
          <h1>{title}</h1>
          <p className="muted">{subtitle}</p>
          {children}
          <p className="auth-footer muted">{footer}</p>
        </div>
      </div>
    </div>
  );
}
