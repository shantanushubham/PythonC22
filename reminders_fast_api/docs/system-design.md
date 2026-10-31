# System design

This document describes how the Reminders API is built and why. It reflects the
code in this repository.

## 1. Goals and scope

**Goals**

- Let users register and authenticate with email and password.
- Let each user create, read, update, and delete their own reminders.
- Keep the code easy to test and to change by separating HTTP, business rules,
  and data access.

**Out of scope today**

- Sending notifications when a reminder is due. The service stores reminders;
  nothing delivers them.
- Roles, admin accounts, or sharing reminders between users.
- Token revocation and logout (see [Known limitations](#9-known-limitations)).

## 2. System context

```mermaid
flowchart LR
    user(["User"])
    swagger["Swagger UI<br/>/docs"]
    postman["Postman"]
    client["Other API client<br/>curl, web, mobile"]
    api["Reminders API<br/>FastAPI"]
    db[("PostgreSQL")]

    user --> swagger
    user --> postman
    user --> client
    swagger -->|HTTP + JWT| api
    postman -->|HTTP + JWT| api
    client -->|HTTP + JWT| api
    api -->|SQLAlchemy / psycopg| db
```

The API is the only component that talks to the database. Clients authenticate
with a JWT sent in the `Authorization: Bearer` header.

## 3. Layered architecture

Each layer depends only on the layer below it.

```mermaid
flowchart TB
    subgraph http["HTTP layer"]
        app["app.py<br/>FastAPI app, middleware, Swagger"]
        uc["controller/user_controller.py"]
        rc["controller/reminder_controller.py"]
    end

    subgraph auth["Auth dependency"]
        ca["core/auth.py<br/>get_current_user, require_self"]
    end

    subgraph biz["Service layer"]
        us["services/user_service.py"]
        rs["services/reminder_service.py"]
    end

    subgraph data["Data access"]
        ur["repositories/user_repository.py"]
        rr["repositories/reminder_repository.py"]
    end

    subgraph store["Persistence"]
        models["models/<br/>User, Reminders"]
        dbpy["core/database.py<br/>engine, session, get_db"]
        pg[("PostgreSQL")]
    end

    subgraph shared["Shared"]
        schemas["schemas/<br/>Pydantic models"]
        sec["utils/security.py<br/>hashing, JWT"]
        log["core/logging_config.py"]
    end

    app --> uc
    app --> rc
    uc --> us
    rc --> rs
    uc --> ca
    rc --> ca
    ca --> ur
    ca --> sec
    us --> ur
    us --> sec
    rs --> rr
    ur --> models
    rr --> models
    models --> dbpy
    dbpy --> pg
    uc -.-> schemas
    rc -.-> schemas
    us -.-> log
    rs -.-> log
    ca -.-> log
    app -.-> log
```

| Layer | Responsibility |
|---|---|
| Controller | Declare routes, validate input with Pydantic, apply auth dependencies, document responses for Swagger |
| Service | Business rules: duplicate email check, ownership check, token issue and refresh, raising `HTTPException` |
| Repository | SQLAlchemy queries and commits. No HTTP concepts |
| Model | Table definitions and relationships |
| `core/auth.py` | Turns a bearer token into the current `User`, or returns 401 |

FastAPI dependency injection wires the layers together. `get_db` yields one
session per request, and `UserService` and `ReminderService` receive it through
their constructors.

```mermaid
classDiagram
    class UserController {
        +create_user()
        +login()
        +refresh_token()
        +get_all_users()
        +get_me()
        +get_user()
        +update_user()
        +delete_user()
    }
    class ReminderController {
        +create_reminder()
        +get_reminders()
        +get_reminder()
        +update_reminder()
        +delete_reminder()
    }
    class UserService {
        +create_user()
        +login()
        +refresh()
        +get_all_users()
        +get_user_by_id()
        +update_user()
        +delete_user()
    }
    class ReminderService {
        +create_reminder()
        +get_reminders()
        +get_reminder()
        +update_reminder()
        +delete_reminder()
    }
    class UserRepository {
        +get_by_id()
        +get_by_email()
        +get_all()
        +create()
        +update()
        +delete()
    }
    class ReminderRepository {
        +get_by_id()
        +get_all()
        +get_by_user_id()
        +create()
        +update()
        +delete()
    }

    UserController --> UserService
    ReminderController --> ReminderService
    UserService --> UserRepository
    ReminderService --> ReminderRepository
```

## 4. Data model

```mermaid
erDiagram
    USERS ||--o{ REMINDERS : owns

    USERS {
        int id PK
        string email UK "unique, not null"
        string hashed_password "Argon2 hash"
        datetime created_at
        datetime updated_at
    }

    REMINDERS {
        int id PK
        string title
        string description
        datetime due_date
        boolean is_completed "false on create"
        datetime created_at
        datetime updated_at
        int user_id FK "references users.id"
    }
```

- `created_at` and `updated_at` are set by the repositories, not by database
  defaults.
- The `User.reminders` relationship uses `cascade="all, delete-orphan"`, so
  deleting a user through the ORM deletes their reminders. The foreign key in
  the database has no `ON DELETE CASCADE`, so deleting a user with raw SQL
  would fail while reminders exist.
- Passwords are stored only as Argon2 hashes (`pwdlib`).

## 5. Authentication and authorization

### 5.1 Tokens

| Token | Lifetime | Used for | `type` claim |
|---|---|---|---|
| Access token | 60 minutes (`JWT_EXPIRE_MINUTES`) | `Authorization: Bearer` on protected routes | `access` |
| Refresh token | 7 days (`JWT_REFRESH_EXPIRE_DAYS`) | `POST /users/refresh` only | `refresh` |

Both are HS256 JWTs signed with `JWT_SECRET`, with claims `sub` (user id),
`type`, and `exp`. The decoder checks `type`, so a refresh token cannot call
protected routes and an access token cannot be refreshed.

### 5.2 Register and log in

```mermaid
sequenceDiagram
    autonumber
    actor C as Client
    participant A as FastAPI app
    participant S as UserService
    participant R as UserRepository
    participant D as PostgreSQL

    C->>A: POST /users/ {email, password}
    A->>S: create_user()
    S->>R: get_by_email()
    R->>D: SELECT user
    D-->>R: none
    S->>S: hash_password (Argon2)
    S->>R: create()
    R->>D: INSERT user
    A-->>C: 201 id, email, timestamps

    C->>A: POST /users/login {email, password}
    A->>S: login()
    S->>R: get_by_email()
    R->>D: SELECT user
    D-->>R: user row
    S->>S: verify_password
    alt wrong email or password
        A-->>C: 401 Incorrect email or password
    else valid
        S->>S: create access + refresh tokens
        A-->>C: 200 access_token, refresh_token
    end
```

A wrong email and a wrong password return the same 401 message, so the response
does not reveal which emails are registered.

### 5.3 Calling a protected route

```mermaid
sequenceDiagram
    autonumber
    actor C as Client
    participant A as FastAPI app
    participant G as get_current_user
    participant R as UserRepository
    participant S as ReminderService
    participant D as PostgreSQL

    C->>A: GET /reminders/ + Bearer access_token
    A->>G: dependency
    G->>G: decode token, require type = access
    alt missing, invalid, expired, or wrong type
        G-->>C: 401 Could not validate credentials
    else valid
        G->>R: get_by_id(sub)
        R->>D: SELECT user
        alt user no longer exists
            G-->>C: 401
        else user found
            G-->>A: current user
            A->>S: get_reminders(current_user.id)
            S->>D: SELECT reminders WHERE user_id = ?
            A-->>C: 200 list
        end
    end
```

### 5.4 Refreshing tokens

```mermaid
sequenceDiagram
    autonumber
    actor C as Client
    participant A as FastAPI app
    participant S as UserService
    participant R as UserRepository

    C->>A: POST /users/refresh {refresh_token}
    A->>S: refresh()
    S->>S: decode token, require type = refresh
    alt invalid, expired, or wrong type
        A-->>C: 401
    else valid
        S->>R: get_by_id(sub)
        alt user deleted
            A-->>C: 401
        else user found
            S->>S: issue new access + refresh tokens
            A-->>C: 200 new token pair
        end
    end
```

### 5.5 Authorization rules

| Resource | Rule | Failure |
|---|---|---|
| `/users/{user_id}` (get, update, delete) | `current_user.id` must equal `user_id` (`require_self`) | `403` |
| `/reminders/*` | Queries are scoped to `current_user.id`. A reminder owned by someone else is treated as missing | `404` |

Returning `404` for another user's reminder, instead of `403`, avoids confirming
that the reminder id exists.

### 5.6 Token lifecycle

```mermaid
stateDiagram-v2
    [*] --> LoggedOut
    LoggedOut --> Active: POST /users/login
    Active --> Active: access token used on protected routes
    Active --> Expired: access token expires after 60 minutes
    Expired --> Active: POST /users/refresh (valid refresh token)
    Expired --> LoggedOut: refresh token also expired
    Active --> LoggedOut: user deleted
```

## 6. Request lifecycle and logging

```mermaid
flowchart TD
    req["Incoming request"] --> mw["log_requests middleware<br/>start timer"]
    mw --> route["Route match"]
    route --> val{"Body and params valid?"}
    val -- no --> e422["422 Unprocessable Entity"]
    val -- yes --> deps["Dependencies<br/>get_db, get_current_user"]
    deps --> auth{"Authenticated?"}
    auth -- no --> e401["401 Unauthorized"]
    auth -- yes --> svc["Service and repository"]
    svc --> ok{"Business rules pass?"}
    ok -- no --> err["4xx HTTPException"]
    ok -- yes --> resp["2xx response"]
    e422 --> logline
    e401 --> logline
    err --> logline
    resp --> logline["Middleware logs<br/>METHOD path -> status (ms)"]
```

- The middleware writes one line per request to the `reminders.app` logger.
- Services and `core/auth.py` log events at `INFO` (success) and `WARNING`
  (rejections) through `reminders.*` loggers.
- Unhandled exceptions are logged with a stack trace and re-raised.
- Passwords and tokens are never written to logs. Failed logins log only
  "Login failed", not the email or password.

## 7. API surface

```mermaid
flowchart LR
    root["/"] --> health["GET / (health)"]

    users["/users"] --> pub["Public"]
    users --> prot["Access token required"]
    pub --> p1["POST / (register)"]
    pub --> p2["POST /login"]
    pub --> p3["POST /refresh"]
    pub --> p4["GET / (list)"]
    prot --> a1["GET /me"]
    prot --> a2["GET /{user_id} (self)"]
    prot --> a3["PUT /{user_id} (self)"]
    prot --> a4["DELETE /{user_id} (self)"]

    reminders["/reminders"] --> r["Access token required"]
    r --> r1["POST /"]
    r --> r2["GET /"]
    r --> r3["GET /{id}"]
    r --> r4["PUT /{id}"]
    r --> r5["DELETE /{id}"]
```

Swagger UI (`/docs`) and ReDoc (`/redoc`) are generated from the route
declarations. The **Authorize** button is backed by the `HTTPBearer` security
scheme in `core/auth.py`.

## 8. Deployment and environments

### 8.1 Local development

```mermaid
flowchart LR
    dev(["Developer"])
    subgraph host["Local machine"]
        uv["uv run uvicorn app:app --reload"]
        env[".env<br/>DATABASE_URL, JWT_SECRET"]
        alembic["uv run alembic upgrade head"]
        subgraph docker["Docker Compose"]
            pg[("PostgreSQL<br/>port 5432<br/>volume postgres_data")]
        end
    end

    dev --> uv
    dev --> alembic
    env --> uv
    uv -->|localhost:5432| pg
    alembic -->|alembic.ini URL| pg
```

### 8.2 Test and CI flow

```mermaid
flowchart LR
    dev(["Developer"]) --> tox["uv run tox"]
    tox --> isort["isort env<br/>isort --check-only"]
    tox --> py["py312 env<br/>pytest"]
    py --> app["FastAPI TestClient"]
    app --> sqlite[("In-memory SQLite<br/>get_db overridden")]
```

Tests replace the `get_db` dependency with an in-memory SQLite session, so they
run without PostgreSQL. Each test gets a fresh database. The suite covers
registration and login, token types and expiry, refresh, ownership rules,
reminder CRUD and pagination, Swagger availability, and logging.

### 8.3 Configuration

All configuration comes from environment variables (see the README). The same
code runs in every environment; only `DATABASE_URL`, `JWT_SECRET`, token
lifetimes, and `LOG_LEVEL` change.

## 9. Known limitations

These are current behaviors worth knowing before using the service beyond local
development.

| Area | Limitation | Possible improvement |
|---|---|---|
| Token revocation | Tokens are stateless. Refreshing issues a new pair, but the old refresh token stays valid until it expires. There is no logout | Store refresh token ids (`jti`) in the database and rotate or revoke them |
| Default secret | If `JWT_SECRET` is unset, a fixed development key is used | Fail at startup when it is missing outside development |
| Public user list | `GET /users/` needs no token and returns every user's email | Require auth, restrict to admins, or remove it |
| Login abuse | No rate limiting or lockout on `/users/login` | Add rate limiting |
| Migrations URL | `alembic.ini` has its own database URL, separate from `DATABASE_URL` | Read `DATABASE_URL` in `alembic/env.py` |
| Timestamps | `created_at` and `updated_at` use naive local time from the app server | Use timezone-aware UTC |
| Schema | `UserUpdate` requires both email and password, and `ReminderUpdate` replaces all fields (PUT semantics) | Add PATCH endpoints with optional fields |
| Password rules | No minimum length or complexity validation | Add validation to `UserCreate` and `UserUpdate` |
| Deletion | Deleting a user relies on the ORM cascade, not a database `ON DELETE CASCADE` | Add the cascade in a migration |
| Reminders | Reminders are stored but never delivered | Add a scheduler or worker for notifications |
| Test database | Tests run on SQLite, while production uses PostgreSQL | Add a PostgreSQL test job for dialect-specific behavior |

## 10. Key decisions

| Decision | Reason |
|---|---|
| Controller, service, and repository layers | Keeps routes thin and lets business rules and queries be tested and changed on their own |
| JWT access token plus refresh token | Short-lived access tokens limit exposure, and refresh tokens avoid asking for the password again |
| `type` claim on tokens | Prevents one token kind from being used where the other is expected |
| Argon2 via `pwdlib` | Current recommended password hashing, with a built-in salt |
| `404` for other users' reminders | Does not reveal which reminder ids exist |
| SQLite for tests via dependency override | Fast, isolated tests with no external services |
| uv with a locked environment, plus tox | Reproducible installs locally and in CI |
