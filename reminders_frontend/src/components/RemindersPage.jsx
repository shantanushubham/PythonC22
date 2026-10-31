import { useCallback, useEffect, useMemo, useState } from 'react'
import { remindersApi } from '../api'
import { useAuth } from '../context/AuthContext'
import { isOverdue, parseDate } from '../utils/dates'
import AccountModal from './AccountModal'
import ReminderForm from './ReminderForm'
import ReminderItem from './ReminderItem'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'pending', label: 'Pending' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'completed', label: 'Completed' },
]

const matchers = {
  all: () => true,
  pending: (r) => !r.is_completed,
  overdue: isOverdue,
  completed: (r) => r.is_completed,
}

// Open reminders first (soonest due on top), then completed (most recent first).
function sortReminders(list) {
  return [...list].sort((a, b) => {
    if (a.is_completed !== b.is_completed) return a.is_completed ? 1 : -1
    const diff = parseDate(a.due_date) - parseDate(b.due_date)
    return a.is_completed ? -diff : diff
  })
}

export default function RemindersPage() {
  const { user, logout } = useAuth()
  const [reminders, setReminders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [formState, setFormState] = useState(null) // null | { reminder: obj|null }
  const [showAccount, setShowAccount] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      setReminders(await remindersApi.list())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [load])

  const counts = useMemo(
    () =>
      Object.fromEntries(
        FILTERS.map((f) => [f.id, reminders.filter(matchers[f.id]).length]),
      ),
    [reminders],
  )

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return sortReminders(
      reminders.filter(
        (r) =>
          matchers[filter](r) &&
          (!q || r.title.toLowerCase().includes(q) || r.description.toLowerCase().includes(q)),
      ),
    )
  }, [reminders, filter, query])

  async function handleSave(values) {
    const existing = formState.reminder
    if (existing) {
      const updated = await remindersApi.update(existing.id, values)
      setReminders((list) => list.map((r) => (r.id === updated.id ? updated : r)))
    } else {
      const created = await remindersApi.create(values)
      // Creation always starts as not completed on the server.
      setReminders((list) => [...list, created])
    }
    setFormState(null)
  }

  async function handleToggle(reminder) {
    setBusyId(reminder.id)
    setError('')
    try {
      const updated = await remindersApi.update(reminder.id, {
        title: reminder.title,
        description: reminder.description,
        due_date: reminder.due_date,
        is_completed: !reminder.is_completed,
      })
      setReminders((list) => list.map((r) => (r.id === updated.id ? updated : r)))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  async function handleDelete(reminder) {
    if (!window.confirm(`Delete "${reminder.title}"?`)) return
    setBusyId(reminder.id)
    setError('')
    try {
      await remindersApi.remove(reminder.id)
      setReminders((list) => list.filter((r) => r.id !== reminder.id))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark">⏰</span>
            <h1>Reminders</h1>
          </div>
          <div className="topbar-right">
            <button type="button" className="link-btn user-email" onClick={() => setShowAccount(true)}>
              {user.email}
            </button>
            <button type="button" className="btn" onClick={logout}>
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="container">
        <div className="toolbar">
          <input
            type="search"
            className="search"
            placeholder="Search reminders…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="button" className="btn primary" onClick={() => setFormState({ reminder: null })}>
            + New reminder
          </button>
        </div>

        <div className="tabs" role="tablist">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              className={filter === f.id ? 'tab active' : 'tab'}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
              <span className="count">{counts[f.id]}</span>
            </button>
          ))}
        </div>

        {error && (
          <div className="alert error">
            {error}{' '}
            <button type="button" className="link-btn" onClick={load}>
              Retry
            </button>
          </div>
        )}

        {loading ? (
          <p className="muted center pad">Loading…</p>
        ) : visible.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">📭</div>
            <p>
              {reminders.length === 0
                ? 'No reminders yet. Add your first one!'
                : 'No reminders match this view.'}
            </p>
          </div>
        ) : (
          <ul className="reminder-list">
            {visible.map((r) => (
              <ReminderItem
                key={r.id}
                reminder={r}
                busy={busyId === r.id}
                onToggle={handleToggle}
                onEdit={(reminder) => setFormState({ reminder })}
                onDelete={handleDelete}
              />
            ))}
          </ul>
        )}
      </main>

      {formState && (
        <ReminderForm
          reminder={formState.reminder}
          onSubmit={handleSave}
          onClose={() => setFormState(null)}
        />
      )}
      {showAccount && <AccountModal onClose={() => setShowAccount(false)} />}
    </>
  )
}
