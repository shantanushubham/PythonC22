import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { usersApi } from '../api'
import { setUnauthorizedHandler, tokenStore } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // If we have a stored token, we're "loading" until /users/me resolves.
  const [loading, setLoading] = useState(() => Boolean(tokenStore.access))

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
  }, [logout])

  useEffect(() => {
    if (!tokenStore.access) return
    let cancelled = false
    usersApi
      .me()
      .then((u) => !cancelled && setUser(u))
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email, password) => {
    const tokens = await usersApi.login(email, password)
    tokenStore.set(tokens)
    setUser(await usersApi.me())
  }, [])

  const register = useCallback(
    async (email, password) => {
      await usersApi.register(email, password)
      await login(email, password)
    },
    [login],
  )

  const value = useMemo(
    () => ({ user, setUser, loading, login, register, logout }),
    [user, loading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
