const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.error || 'Something went wrong')
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
  return request('/users/create/', {
    method: 'POST',
    body: JSON.stringify(user),
  })
}

export function getUserTasks(userId) {
  return request(`/users/${userId}/tasks/`)
}

export function createTask(task) {
  return request('/tasks/create/', {
    method: 'POST',
    body: JSON.stringify(task),
  })
}

export function updateTask(taskId, task) {
  return request(`/tasks/${taskId}/update/`, {
    method: 'PUT',
    body: JSON.stringify(task),
  })
}

export function deleteTask(taskId) {
  return request(`/tasks/${taskId}/delete/`, {
    method: 'DELETE',
  })
}
