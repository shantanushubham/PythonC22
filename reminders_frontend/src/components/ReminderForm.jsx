import { useState } from 'react'
import Modal from './Modal'
import { defaultDueInput, toApiValue, toInputValue } from '../utils/dates'

// `reminder` is null when creating, or the existing reminder when editing.
export default function ReminderForm({ reminder, onSubmit, onClose }) {
  const editing = Boolean(reminder)
  const [title, setTitle] = useState(reminder?.title ?? '')
  const [description, setDescription] = useState(reminder?.description ?? '')
  const [due, setDue] = useState(reminder ? toInputValue(reminder.due_date) : defaultDueInput())
  const [completed, setCompleted] = useState(reminder?.is_completed ?? false)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      await onSubmit({
        title: title.trim(),
        description: description.trim(),
        due_date: toApiValue(due),
        is_completed: completed,
      })
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <Modal title={editing ? 'Edit reminder' : 'New reminder'} onClose={onClose}>
      <form className="form" onSubmit={handleSubmit}>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus required />
        </label>
        <label>
          Description
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label>
          Due
          <input
            type="datetime-local"
            value={due}
            onChange={(e) => setDue(e.target.value)}
            required
          />
        </label>
        {editing && (
          <label className="checkbox">
            <input
              type="checkbox"
              checked={completed}
              onChange={(e) => setCompleted(e.target.checked)}
            />
            Completed
          </label>
        )}

        {error && <div className="alert error">{error}</div>}

        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn primary" disabled={saving}>
            {saving ? 'Saving…' : editing ? 'Save changes' : 'Add reminder'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
