# Reminders Frontend

React (Vite) client for the FastAPI app in `../reminders_fast_api`.

## Features

- Register / sign in (JWT access + refresh tokens, automatic refresh on 401)
- Create, edit, complete/uncomplete and delete reminders
- Filter (All / Pending / Overdue / Completed) and search
- Account dialog: change email/password, delete account
- Light/dark theme following the OS setting

## Run

Start the backend (from `../reminders_fast_api`):

```bash
uvicorn app:app --port 8000
```

Then the frontend:

```bash
npm install
npm run dev     # http://localhost:5173
```

## How it talks to the API

The backend has no CORS middleware, so in dev the Vite server proxies
`/api/*` to `http://127.0.0.1:8000` (stripping the `/api` prefix). The browser
only ever talks to the Vite origin.

| Variable                  | Purpose                                                        | Default                 |
| ------------------------- | -------------------------------------------------------------- | ----------------------- |
| `VITE_API_PROXY_TARGET`   | Where the Vite proxy forwards `/api`                           | `http://127.0.0.1:8000` |
| `VITE_API_BASE_URL`       | Call the API directly instead (backend must enable CORS)       | `/api`                  |

## Scripts

- `npm run dev` – dev server
- `npm run build` – production build to `dist/`
- `npm run preview` – serve the build (also proxies `/api`)
- `npm run lint` – oxlint

## Layout

```
src/
  api/          fetch client (token handling) + endpoint functions
  context/      AuthContext (session state)
  components/   AuthPage, RemindersPage, ReminderItem, ReminderForm, AccountModal, Modal
  utils/dates.js
```
