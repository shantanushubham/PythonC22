import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login, register, loading, error, clearError } = useAuth()
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')

  const isLogin = mode === 'login'
  const canSubmit = isLogin
    ? username.trim()
    : username.trim() && email.trim()

  async function handleSubmit(event) {
    event.preventDefault()
    if (!canSubmit) return

    if (isLogin) {
      await login(username.trim())
    } else {
      await register(username.trim(), email.trim())
    }
  }

  function switchMode(nextMode) {
    setMode(nextMode)
    setUsername('')
    setEmail('')
    clearError()
  }

  return (
    <div className="auth-card">
      <div className="auth-header">
        <h1>Task Manager</h1>
        <p>
          {isLogin
            ? 'Sign in with your username to manage tasks.'
            : 'Create an account to start managing tasks.'}
        </p>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label htmlFor="username">Username</label>
        <input
          id="username"
          type="text"
          placeholder="e.g. shantanu"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          disabled={loading}
        />

        {!isLogin && (
          <>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              disabled={loading}
            />
          </>
        )}

        {error && <p className="error">{error}</p>}

        <button type="submit" disabled={loading || !canSubmit}>
          {loading
            ? isLogin
              ? 'Signing in…'
              : 'Creating account…'
            : isLogin
              ? 'Sign in'
              : 'Create account'}
        </button>
      </form>

      <p className="hint">
        {isLogin ? (
          <>
            Try: shantanu, basant, or manoj.{' '}
            <button
              type="button"
              className="link-button"
              onClick={() => switchMode('register')}
            >
              Create a new account
            </button>
          </>
        ) : (
          <>
            Already have an account?{' '}
            <button
              type="button"
              className="link-button"
              onClick={() => switchMode('login')}
            >
              Sign in
            </button>
          </>
        )}
      </p>
    </div>
  )
}
