import { useCallback, useEffect, useState } from 'react'
import {
  createTask,
  deleteTask,
  getUserTasks,
  patchTask,
  updateTask,
} from '../api'
import { useAuth } from '../context/AuthContext'
import TaskForm from './TaskForm'

function formatDate(value) {
  if (!value) return 'No due date'
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return new Date(`${value}T00:00:00`).toLocaleDateString()
  }
  return new Date(value).toLocaleString()
}

export default function TaskDashboard() {
  const { user, logout } = useAuth()
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editingTask, setEditingTask] = useState(null)
  const [showForm, setShowForm] = useState(false)

  const loadTasks = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getUserTasks(user.id)
      setTasks(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [user.id])

  useEffect(() => {
    loadTasks()
  }, [loadTasks])

  async function handleCreate(payload) {
    await createTask({ ...payload, user: user.id })
    setShowForm(false)
    await loadTasks()
  }

  async function handleUpdate(payload) {
    await updateTask(editingTask.id, { ...payload, user: user.id })
    setEditingTask(null)
    await loadTasks()
  }

  async function handleDelete(taskId) {
    if (!window.confirm('Delete this task?')) return
    await deleteTask(taskId)
    await loadTasks()
  }

  async function handleToggleComplete(task) {
    await patchTask(task.id, { completed: !task.completed })
    await loadTasks()
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div>
          <h1>My Tasks</h1>
          <p>
            Signed in as <strong>{user.username}</strong>
          </p>
        </div>
        <button type="button" className="secondary" onClick={logout}>
          Log out
        </button>
      </header>

      <div className="dashboard-actions">
        <button
          type="button"
          onClick={() => {
            setEditingTask(null)
            setShowForm(true)
          }}
        >
          + Add task
        </button>
      </div>

      {(showForm || editingTask) && (
        <TaskForm
          task={editingTask}
          onSubmit={editingTask ? handleUpdate : handleCreate}
          onCancel={() => {
            setShowForm(false)
            setEditingTask(null)
          }}
        />
      )}

      {loading && <p className="status">Loading tasks…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && tasks.length === 0 && (
        <p className="status">No tasks yet. Create your first one above.</p>
      )}

      <ul className="task-list">
        {tasks.map((task) => (
          <li key={task.id} className={task.completed ? 'completed' : ''}>
            <label className="task-check">
              <input
                type="checkbox"
                checked={task.completed}
                onChange={() => handleToggleComplete(task)}
              />
              <span>{task.title}</span>
            </label>

            {task.description && <p>{task.description}</p>}
            <p className="meta">Due: {formatDate(task.due_date)}</p>

            <div className="task-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setShowForm(false)
                  setEditingTask(task)
                }}
              >
                Edit
              </button>
              <button
                type="button"
                className="danger"
                onClick={() => handleDelete(task.id)}
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
