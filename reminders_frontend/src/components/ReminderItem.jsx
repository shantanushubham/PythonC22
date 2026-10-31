import { formatDue, formatRelative, isOverdue } from '../utils/dates'

export default function ReminderItem({ reminder, busy, onToggle, onEdit, onDelete }) {
  const overdue = isOverdue(reminder)
  const cls = ['reminder', reminder.is_completed && 'done', overdue && 'overdue']
    .filter(Boolean)
    .join(' ')

  return (
    <li className={cls}>
      <input
        type="checkbox"
        className="reminder-check"
        checked={reminder.is_completed}
        disabled={busy}
        onChange={() => onToggle(reminder)}
        aria-label={`Mark "${reminder.title}" as ${reminder.is_completed ? 'not completed' : 'completed'}`}
      />
      <div className="reminder-body">
        <div className="reminder-title">{reminder.title}</div>
        {reminder.description && <div className="reminder-desc">{reminder.description}</div>}
        <div className="reminder-meta">
          <span>📅 {formatDue(reminder.due_date)}</span>
          {!reminder.is_completed && (
            <span className={overdue ? 'badge danger' : 'badge'}>
              {overdue ? 'Overdue · ' : ''}
              {formatRelative(reminder.due_date)}
            </span>
          )}
          {reminder.is_completed && <span className="badge success">Completed</span>}
        </div>
      </div>
      <div className="reminder-actions">
        <button type="button" className="icon-btn" onClick={() => onEdit(reminder)} disabled={busy} title="Edit">
          ✎
        </button>
        <button
          type="button"
          className="icon-btn danger"
          onClick={() => onDelete(reminder)}
          disabled={busy}
          title="Delete"
        >
          🗑
        </button>
      </div>
    </li>
  )
}
