import { useEffect, useState } from 'react'

const emptyForm = {
  title: '',
  description: '',
  due_date: '',
  completed: false,
}

function toInputDate(value) {
  if (!value) return ''
  return value.slice(0, 16)
}

function toApiDate(value) {
  if (!value) return null
  return `${value}:00Z`
}

export default function TaskForm({ task, onSubmit, onCancel }) {
  const [form, setForm] = useState(emptyForm)

  useEffect(() => {
    if (task) {
      setForm({
        title: task.title,
        description: task.description || '',
        due_date: toInputDate(task.due_date),
        completed: task.completed,
      })
    } else {
      setForm(emptyForm)
    }
  }, [task])

  function handleChange(event) {
    const { name, value, type, checked } = event.target
    setForm((current) => ({
      ...current,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    onSubmit({
      title: form.title.trim(),
      description: form.description.trim(),
      due_date: toApiDate(form.due_date),
      completed: form.completed,
    })
  }

  return (
    <form className="task-form" onSubmit={handleSubmit}>
      <h2>{task ? 'Edit task' : 'New task'}</h2>

      <label htmlFor="title">Title</label>
      <input
        id="title"
        name="title"
        type="text"
        value={form.title}
        onChange={handleChange}
        placeholder="What needs to be done?"
        required
      />

      <label htmlFor="description">Description</label>
      <textarea
        id="description"
        name="description"
        value={form.description}
        onChange={handleChange}
        placeholder="Optional details"
        rows={3}
      />

      <label htmlFor="due_date">Due date</label>
      <input
        id="due_date"
        name="due_date"
        type="datetime-local"
        value={form.due_date}
        onChange={handleChange}
      />

      <label className="checkbox-row">
        <input
          name="completed"
          type="checkbox"
          checked={form.completed}
          onChange={handleChange}
        />
        Mark as completed
      </label>

      <div className="form-actions">
        <button type="submit">{task ? 'Save changes' : 'Create task'}</button>
        {onCancel && (
          <button type="button" className="secondary" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
