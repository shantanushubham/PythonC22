import { createContext, useContext, useMemo, useState } from 'react'
import { createUser as createUserRequest, login as loginRequest } from '../api'

const AuthContext = createContext(null)

const STORAGE_KEY = 'task_app_user'

function getStoredUser() {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getStoredUser)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function login(username) {
    setLoading(true)
    setError('')
    try {
      const loggedInUser = await loginRequest(username)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(loggedInUser))
      setUser(loggedInUser)
      return loggedInUser
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  async function register(username, email) {
    setLoading(true)
    setError('')
    try {
      const newUser = await createUserRequest({ username, email })
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newUser))
      setUser(newUser)
      return newUser
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  function clearError() {
    setError('')
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY)
    setUser(null)
    setError('')
  }

  const value = useMemo(
    () => ({ user, loading, error, login, register, logout, clearError }),
    [user, loading, error],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
