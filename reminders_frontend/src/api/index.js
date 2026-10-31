import { request } from './client'

export const usersApi = {
  register: (email, password) =>
    request('/users/', { method: 'POST', auth: false, body: { email, password } }),
  login: (email, password) =>
    request('/users/login', { method: 'POST', auth: false, body: { email, password } }),
  me: () => request('/users/me'),
  // The API requires both email and password on update.
  update: (id, email, password) =>
    request(`/users/${id}`, { method: 'PUT', body: { email, password } }),
  remove: (id) => request(`/users/${id}`, { method: 'DELETE' }),
}

export const remindersApi = {
  list: () => request('/reminders/?skip=0&limit=1000'),
  create: ({ title, description, due_date }) =>
    request('/reminders/', { method: 'POST', body: { title, description, due_date } }),
  update: (id, { title, description, due_date, is_completed }) =>
    request(`/reminders/${id}`, {
      method: 'PUT',
      body: { title, description, due_date, is_completed },
    }),
  remove: (id) => request(`/reminders/${id}`, { method: 'DELETE' }),
}
