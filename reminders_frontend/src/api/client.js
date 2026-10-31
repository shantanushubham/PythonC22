// Thin fetch wrapper: attaches the bearer token, and on a 401 transparently
// tries POST /users/refresh once before giving up and signalling logout.

// Override with VITE_API_BASE_URL to call the API directly (requires CORS on the backend).
export const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const ACCESS_KEY = 'reminders.access_token'
const REFRESH_KEY = 'reminders.refresh_token'

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS_KEY)
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY)
  },
  set({ access_token, refresh_token }) {
    localStorage.setItem(ACCESS_KEY, access_token)
    localStorage.setItem(REFRESH_KEY, refresh_token)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

// FastAPI errors: { detail: "msg" } or { detail: [{ loc, msg }, ...] } for 422.
function extractMessage(data, status) {
  const detail = data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : null
        return field ? `${field}: ${d.msg}` : d.msg
      })
      .join('; ')
  }
  return `Request failed (${status})`
}

async function parse(res) {
  if (res.status === 204) return null
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

async function send(path, { method = 'GET', body, auth = true, token } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const bearer = token ?? (auth ? tokenStore.access : null)
  if (bearer) headers.Authorization = `Bearer ${bearer}`

  let res
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(
      'Cannot reach the server. Is the Reminders API running?',
      0,
      null,
    )
  }
  return res
}

// Share one in-flight refresh across concurrent 401s.
let refreshing = null
async function refreshTokens() {
  if (!tokenStore.refresh) return false
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await send('/users/refresh', {
          method: 'POST',
          auth: false,
          body: { refresh_token: tokenStore.refresh },
        })
        if (!res.ok) return false
        tokenStore.set(await parse(res))
        return true
      } catch {
        return false
      } finally {
        refreshing = null
      }
    })()
  }
  return refreshing
}

export async function request(path, options = {}) {
  let res = await send(path, options)

  if (res.status === 401 && options.auth !== false) {
    if (await refreshTokens()) {
      res = await send(path, options)
    }
    if (res.status === 401) {
      tokenStore.clear()
      onUnauthorized()
    }
  }

  const data = await parse(res)
  if (!res.ok) throw new ApiError(extractMessage(data, res.status), res.status, data)
  return data
}
