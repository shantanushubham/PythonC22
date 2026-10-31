# Reminders API

A FastAPI service for managing users and their reminders. Users register, log in
with email and password, and receive a short-lived JWT access token plus a
longer-lived refresh token. Each user can only see and change their own
reminders.

- **Stack:** FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, PyJWT, pwdlib (Argon2)
- **Tooling:** uv, pytest, isort, tox
- **Design notes:** [docs/system-design.md](docs/system-design.md)

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker (for the local PostgreSQL database)

## Quick start

Run these from the project root.

```bash
# 1. Install dependencies (creates .venv)
uv sync

# 2. Start PostgreSQL
docker compose up -d db

# 3. Create .env, then set JWT_SECRET (see "Configuration" below)
cp .env.example .env

# 4. Create the tables
uv run alembic upgrade head

# 5. Run the API with auto-reload
uv run uvicorn app:app --reload
```

The API is now at <http://127.0.0.1:8000>.

| URL | What it is |
|---|---|
| <http://127.0.0.1:8000/docs> | Swagger UI |
| <http://127.0.0.1:8000/redoc> | ReDoc |
| <http://127.0.0.1:8000/openapi.json> | OpenAPI schema |

## Configuration

Settings are read from environment variables. `.env` is loaded automatically and
is git-ignored.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://reminders:reminders@localhost:5432/reminders` | SQLAlchemy connection string used by the app |
| `JWT_SECRET` | `dev-only-change-me` | Key that signs tokens. **Always set this**, and use at least 32 characters |
| `JWT_EXPIRE_MINUTES` | `60` | Access token lifetime |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `LOG_LEVEL` | `INFO` | Level for the `reminders.*` loggers |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_PORT` | `reminders` / `reminders` / `reminders` / `5432` | Used by `docker-compose.yml` |

`.env.example` lists the variables with safe placeholder values. Copy it to
`.env` and replace `JWT_SECRET`. Generate a secret with:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

> **Alembic uses its own URL.** Migrations read `sqlalchemy.url` from
> `alembic.ini`, not `DATABASE_URL`. If you change the database host, user, or
> password, update `alembic.ini` as well.

## Trying the API

### In Swagger UI

1. Open `/docs`.
2. Run **POST /users/** to register.
3. Run **POST /users/login** and copy the `access_token` from the response.
4. Click **Authorize**, paste the token (without the `Bearer ` prefix), and confirm.
5. Call any protected route, such as **POST /reminders/**.

### With curl

```bash
BASE=http://127.0.0.1:8000

# Register
curl -X POST $BASE/users/ -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"secret-pass"}'

# Log in
curl -X POST $BASE/users/login -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"secret-pass"}'
# -> {"access_token":"...","refresh_token":"...","token_type":"bearer"}

TOKEN=<access_token from the response>

# Create a reminder
curl -X POST $BASE/reminders/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Pay rent","description":"Monthly","due_date":"2026-11-01T12:00:00"}'

# List my reminders
curl $BASE/reminders/ -H "Authorization: Bearer $TOKEN"

# Get a new token pair when the access token expires
curl -X POST $BASE/users/refresh -H 'Content-Type: application/json' \
  -d '{"refresh_token":"<refresh_token>"}'
```

### With Postman

Import both files from the `postman/` folder:

- `Reminders API.postman_collection.json`
- `Reminders Local.postman_environment.json`

Select the **Reminders Local** environment, set `email` and `password`, then
send the requests from top to bottom. Login and refresh requests save the tokens
for later requests. Run **Delete user** last.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | none | Health check |
| `POST` | `/users/` | none | Register |
| `POST` | `/users/login` | none | Get access and refresh tokens |
| `POST` | `/users/refresh` | refresh token in body | Get a new token pair |
| `GET` | `/users/` | none | List users (`skip`, `limit`) |
| `GET` | `/users/me` | access token | Current user |
| `GET` | `/users/{user_id}` | access token, self only | Get a user |
| `PUT` | `/users/{user_id}` | access token, self only | Update email and password |
| `DELETE` | `/users/{user_id}` | access token, self only | Delete a user and their reminders |
| `POST` | `/reminders/` | access token | Create a reminder |
| `GET` | `/reminders/` | access token | List my reminders (`skip`, `limit`) |
| `GET` | `/reminders/{id}` | access token | Get one of my reminders |
| `PUT` | `/reminders/{id}` | access token | Replace one of my reminders |
| `DELETE` | `/reminders/{id}` | access token | Delete one of my reminders |

Status codes you can expect:

- `400` email already registered
- `401` missing, invalid, or expired token, or wrong email or password
- `403` accessing another user's account
- `404` unknown reminder or user, or a reminder owned by someone else
- `422` request body failed validation

## Local development

### Project layout

```text
app.py                 FastAPI app, Swagger metadata, request logging middleware
controller/            HTTP routes (user_controller.py, reminder_controller.py)
services/              Business rules and error handling
repositories/          Database queries
models/                SQLAlchemy models
schemas/               Pydantic request and response models
core/                  database.py, auth.py (JWT dependency), logging_config.py
utils/security.py      Password hashing and JWT helpers
alembic/               Database migrations
tests/                 pytest suite
postman/               Importable Postman collection and environment
docs/                  System design
```

A request flows `controller -> service -> repository -> database`. See
[docs/system-design.md](docs/system-design.md) for diagrams.

### Running the tests

The tests use an in-memory SQLite database, so PostgreSQL does not need to be
running.

```bash
uv run pytest                      # all tests
uv run pytest tests/test_users.py  # one file
uv run pytest -k refresh           # tests matching a name
```

### Import sorting

```bash
uv run isort .                  # sort imports in place
uv run isort --check-only .     # check without changing files
```

### tox

tox runs the import check and the test suite in clean environments (using
`tox-uv` and the locked dependencies).

```bash
uv run tox                # isort check + tests
uv run tox -e isort       # import check only
uv run tox -e py312       # tests only
uv run tox -e format      # sort imports in place
```

### Database migrations

```bash
# Apply all migrations
uv run alembic upgrade head

# After changing a model, generate a migration, review it, then apply it
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head

# Undo the last migration
uv run alembic downgrade -1
```

New models must be imported in `alembic/env.py` so autogenerate can see them.

### Logging

Logs go to stdout in this format:

```text
2026-10-31 12:45:19,686 INFO     reminders.app: POST /users/ -> 201 (106.3 ms)
2026-10-31 12:45:19,737 WARNING  reminders.user_service: Login failed
```

- `reminders.app` logs every request with its status and duration.
- Services and the auth dependency log events such as registrations, failed
  logins, and rejected tokens.
- Passwords and tokens are never logged.

Set `LOG_LEVEL=DEBUG` to see more detail.

### Resetting the database

```bash
docker compose down -v     # stops PostgreSQL and deletes its data volume
docker compose up -d db
uv run alembic upgrade head
```

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `connection refused` on startup or first request | PostgreSQL is not running. Run `docker compose up -d db`. |
| `relation "users" does not exist` | Migrations have not been applied. Run `uv run alembic upgrade head`. |
| `401` on every protected call | Paste only the `access_token` into Authorize, and do not use the refresh token. Check the token has not expired. |
| All tokens stop working after a restart | `JWT_SECRET` changed or is unset. Log in again after setting a stable secret in `.env`. |
| `Address already in use` | Another process is on port 8000. Use `--port 8001` or stop the other process. |
| Alembic connects to the wrong database | Update `sqlalchemy.url` in `alembic.ini`. |
