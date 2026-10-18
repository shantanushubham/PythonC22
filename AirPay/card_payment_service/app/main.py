"""FastAPI application for the mock card payment service."""

import logging
import os

from fastapi import FastAPI

from app.controllers import health_controller, openapi_controller, payment_controller
from app.error_handlers import register_error_handlers
from app.openapi import DESCRIPTION, TAGS, build_openapi


def create_app() -> FastAPI:
    app = FastAPI(
        title="Card Payment Service",
        version="1.0.0",
        summary="Mock card network for debit and credit card payments.",
        description=DESCRIPTION,
        openapi_tags=TAGS,
    )
    app.openapi = lambda: build_openapi(app)  # type: ignore[method-assign]

    register_error_handlers(app)
    app.include_router(health_controller.router)
    app.include_router(openapi_controller.router)
    app.include_router(payment_controller.router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
