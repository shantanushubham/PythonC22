import { useState } from 'react'
import Modal from './Modal'
import { usersApi } from '../api'
import { useAuth } from '../context/AuthContext'

export default function AccountModal({ onClose }) {
  const { user, setUser, logout } = useAuth()
  const [email, setEmail] = useState(user.email)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  async function handleSave(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    setSaving(true)
    try {
      // The API replaces both fields, so a password is required to save.
      setUser(await usersApi.update(user.id, email.trim(), password))
      setPassword('')
      setSuccess('Account updated.')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    setError('')
    try {
      await usersApi.remove(user.id)
      logout()
    } catch (err) {
      setError(err.message)
      setConfirmingDelete(false)
    }
  }

  return (
    <Modal title="Account" onClose={onClose}>
      <form className="form" onSubmit={handleSave}>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          New password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            placeholder="Enter your password (new or current)"
            required
          />
        </label>
        <p className="muted small">
          Saving sets your password to the value above, so enter your current password to keep it.
        </p>

        {error && <div className="alert error">{error}</div>}
        {success && <div className="alert success">{success}</div>}

        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>
            Close
          </button>
          <button type="submit" className="btn primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>

      <hr />
      <div className="danger-zone">
        <div>
          <strong>Delete account</strong>
          <p className="muted small">Permanently removes your account.</p>
        </div>
        {confirmingDelete ? (
          <div className="inline-actions">
            <button type="button" className="btn" onClick={() => setConfirmingDelete(false)}>
              Cancel
            </button>
            <button type="button" className="btn danger" onClick={handleDelete}>
              Yes, delete
            </button>
          </div>
        ) : (
          <button type="button" className="btn danger-outline" onClick={() => setConfirmingDelete(true)}>
            Delete
          </button>
        )}
      </div>
    </Modal>
  )
}
