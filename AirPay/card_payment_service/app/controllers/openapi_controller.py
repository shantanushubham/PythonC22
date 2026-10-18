"""Serves the OpenAPI spec.

`/openapi.json` is FastAPI's built-in path. `/openapi` returns the same document.
Neither endpoint is listed in the spec itself.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(include_in_schema=False)


@router.get("/openapi")
def openapi_spec(request: Request) -> JSONResponse:
    return JSONResponse(request.app.openapi())
