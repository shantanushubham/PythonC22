"""Build JSON responses from serializer models."""

from fastapi.responses import JSONResponse
from pydantic import BaseModel


def json_response(
    model: BaseModel,
    status_code: int,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Serialize `model`, leaving out fields that are None."""
    return JSONResponse(
        status_code=status_code,
        content=model.model_dump(mode="json", exclude_none=True),
        headers=headers,
    )
