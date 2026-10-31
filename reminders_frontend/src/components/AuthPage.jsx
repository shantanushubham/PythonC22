import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

export default function AuthPage() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const isLogin = mode === 'login'

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await (isLogin ? login : register)(email.trim(), password)
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  function switchMode() {
    setMode(isLogin ? 'register' : 'login')
    setError('')
  }

  return (
    <main className="auth-page">
      <form className="card auth-card" onSubmit={handleSubmit}>
        <div className="brand">
          <span className="brand-mark">⏰</span>
          <h1>Reminders</h1>
        </div>
        <p className="muted">
          {isLogin ? 'Sign in to see your reminders.' : 'Create an account to get started.'}
        </p>

        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            autoFocus
            required
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={isLogin ? 'current-password' : 'new-password'}
            required
          />
        </label>

        {error && <div className="alert error">{error}</div>}

        <button type="submit" className="btn primary" disabled={submitting}>
          {submitting ? 'Please wait…' : isLogin ? 'Sign in' : 'Create account'}
        </button>

        <p className="muted center">
          {isLogin ? "Don't have an account? " : 'Already have an account? '}
          <button type="button" className="link-btn" onClick={switchMode}>
            {isLogin ? 'Register' : 'Sign in'}
          </button>
        </p>
      </form>
    </main>
  )
}
