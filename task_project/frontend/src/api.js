const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

function getErrorMessage(data) {
  if (!data || typeof data !== 'object') return 'Something went wrong'
  if (typeof data.error === 'string') return data.error
  if (typeof data.detail === 'string') return data.detail

  const first = Object.values(data)[0]
  if (Array.isArray(first) && first[0]) return String(first[0])
  if (typeof first === 'string') return first

  return 'Something went wrong'
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  const text = await response.text()
  const data = text ? JSON.parse(text) : {}

  if (!response.ok) {
    throw new Error(getErrorMessage(data))
  }

  return data
}

export function login(username) {
  return request('/login/', {
    method: 'POST',
    body: JSON.stringify({ username }),
  })
}

export function createUser(user) {
  return request('/users/', {
    method: 'POST',
    body: JSON.stringify(user),
  })
}

export function getUserTasks(userId) {
  return request(`/users/${userId}/tasks/`)
}

export function createTask(task) {
  return request('/tasks/', {
    method: 'POST',
    body: JSON.stringify(task),
  })
}

export function updateTask(taskId, task) {
  return request(`/tasks/${taskId}/`, {
    method: 'PUT',
    body: JSON.stringify(task),
  })
}

export function patchTask(taskId, task) {
  return request(`/tasks/${taskId}/`, {
    method: 'PATCH',
    body: JSON.stringify(task),
  })
}

export function deleteTask(taskId) {
  return request(`/tasks/${taskId}/`, {
    method: 'DELETE',
  })
}
