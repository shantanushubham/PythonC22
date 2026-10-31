// The API stores naive (timezone-less) datetimes in server-local time, so we
// treat them as local time on the client too.

const pad = (n) => String(n).padStart(2, '0')

export function parseDate(value) {
  return new Date(value)
}

// Date -> value for <input type="datetime-local">
export function toInputValue(date) {
  const d = date instanceof Date ? date : new Date(date)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// <input type="datetime-local"> value -> API payload (naive ISO)
export function toApiValue(inputValue) {
  return inputValue.length === 16 ? `${inputValue}:00` : inputValue
}

export function defaultDueInput() {
  const d = new Date()
  d.setHours(d.getHours() + 1, 0, 0, 0)
  return toInputValue(d)
}

export function isOverdue(reminder) {
  return !reminder.is_completed && parseDate(reminder.due_date) < new Date()
}

const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

export function formatDue(value) {
  return dateTimeFmt.format(parseDate(value))
}

const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

export function formatRelative(value) {
  const diffMs = parseDate(value) - new Date()
  const abs = Math.abs(diffMs)
  const units = [
    ['day', 86_400_000],
    ['hour', 3_600_000],
    ['minute', 60_000],
  ]
  for (const [unit, ms] of units) {
    if (abs >= ms) return rtf.format(Math.round(diffMs / ms), unit)
  }
  return 'now'
}
