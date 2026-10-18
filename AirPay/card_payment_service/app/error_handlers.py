"""Error handlers: turn every failure into the standard error response."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exceptions import DomainError
from app.responses import json_response
from app.schemas import ErrorResponse

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _request_validation_error)
    app.add_exception_handler(404, _route_not_found)
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)


async def _domain_error(_request: Request, exc: DomainError) -> JSONResponse:
    body = ErrorResponse(message=exc.message, errors=exc.errors)
    return json_response(body, exc.status_code)


async def _request_validation_error(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        location = [
            str(part)
            for part in error.get("loc", [])
            if part not in ("body", "query", "path", "header")
        ]
        errors.append({"field": ".".join(location) or "body", "message": _clean_message(error)})
    return JSONResponse(
        status_code=400,
        content={"success": False, "message": "Validation failed", "errors": errors},
    )


async def _route_not_found(request: Request, _exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": f"Route {request.method} {request.url.path} not found",
        },
    )


async def _http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(status_code=exc.status_code, content={"success": False, "message": message})


async def _unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error"},
    )


def _clean_message(error: dict) -> str:
    message = str(error.get("msg", "Invalid value"))
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message
