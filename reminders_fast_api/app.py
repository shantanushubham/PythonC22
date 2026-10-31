import time

from fastapi import FastAPI, Request

from controller.reminder_controller import router as reminder_router
from controller.user_controller import router as user_router
from core.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger("app")

DESCRIPTION = """
Manage users and their reminders.

## Authentication

1. Register with `POST /users/`.
2. Log in with `POST /users/login` to get an `access_token` and a `refresh_token`.
3. Click **Authorize** above and paste the `access_token` (no `Bearer ` prefix).
4. When the access token expires, call `POST /users/refresh` with the refresh token.

Reminder routes only return the signed-in user's reminders.
"""

TAGS_METADATA = [
    {"name": "users", "description": "Register, log in, refresh tokens, and manage users."},
    {"name": "reminders", "description": "Create and manage the signed-in user's reminders."},
    {"name": "health", "description": "Service status."},
]

app = FastAPI(
    title="Reminders API",
    version="1.0.0",
    description=DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("%s %s failed", request.method, request.url.path)
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(user_router)
app.include_router(reminder_router)


@app.get("/", tags=["health"], summary="Health check")
def read_root():
    return {"message": "Hello, World!"}
