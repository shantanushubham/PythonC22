import { AuthProvider, useAuth } from './context/AuthContext'
import AuthPage from './components/AuthPage'
import RemindersPage from './components/RemindersPage'
import './App.css'

function Gate() {
  const { user, loading } = useAuth()
  if (loading) return <p className="muted center pad">Loading…</p>
  return user ? <RemindersPage /> : <AuthPage />
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  )
}
