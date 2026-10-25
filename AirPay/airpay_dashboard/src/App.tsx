import { lazy } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Spinner } from "./components/ui";
import { useAuth } from "./auth/AuthContext";
import ApiKeys from "./pages/ApiKeys";
import BankAccounts from "./pages/BankAccounts";
import Balance from "./pages/Balance";
import Checkout from "./pages/Checkout";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import PayReturn from "./pages/PayReturn";
import Payouts from "./pages/Payouts";
import Profile from "./pages/Profile";
import Refunds from "./pages/Refunds";
import Register from "./pages/Register";
import TransactionDetail from "./pages/TransactionDetail";
import Transactions from "./pages/Transactions";

// The dashboard pulls in the charts library, so it is loaded on demand.
const Dashboard = lazy(() => import("./pages/Dashboard"));

function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Spinner label="Restoring your session…" />;
  if (status === "anon") return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <Layout />;
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === "loading") return <Spinner />;
  if (status === "authed") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
      <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
      <Route element={<RequireAuth />}>
        <Route index element={<Dashboard />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="transactions/:id" element={<TransactionDetail />} />
        <Route path="collect" element={<Checkout />} />
        <Route path="pay/return" element={<PayReturn />} />
        <Route path="refunds" element={<Refunds />} />
        <Route path="balance" element={<Balance />} />
        <Route path="payouts" element={<Payouts />} />
        <Route path="bank-accounts" element={<BankAccounts />} />
        <Route path="api-keys" element={<ApiKeys />} />
        <Route path="profile" element={<Profile />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
