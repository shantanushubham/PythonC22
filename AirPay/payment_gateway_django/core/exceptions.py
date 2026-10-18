"""One error shape for the whole API.

Every error response looks like this, the same as the AirPay mock services:

    {"success": false,
     "message": "Validation failed",
     "errors": [{"field": "amount", "message": "A valid number is required."}]}

`errors` is only present for validation problems.
"""

import logging

from django.http import Http404, JsonResponse
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)

NON_FIELD = "body"


def error_body(message: str, errors: list[dict[str, str]] | None = None) -> dict:
    body: dict = {"success": False, "message": message}
    if errors:
        body["errors"] = errors
    return body


def flatten_validation_errors(detail, prefix: str = "") -> list[dict[str, str]]:
    """Turn DRF's nested error structure into a flat list of field/message pairs.

    {"items": [{"qty": ["Too small."]}]} becomes [{"field": "items.0.qty", ...}].
    """
    if isinstance(detail, dict):
        flat: list[dict[str, str]] = []
        for key, value in detail.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flat.extend(flatten_validation_errors(value, path))
        return flat

    if isinstance(detail, list):
        flat = []
        for index, item in enumerate(detail):
            if isinstance(item, (dict, list)):
                path = f"{prefix}.{index}" if prefix else str(index)
                flat.extend(flatten_validation_errors(item, path))
            else:
                flat.append({"field": prefix or NON_FIELD, "message": str(item)})
        return flat

    return [{"field": prefix or NON_FIELD, "message": str(detail)}]


def api_exception_message(exc: exceptions.APIException) -> str:
    """The human readable message of an API exception.

    Most exceptions carry a plain string. The JWT library's token errors carry a dict
    such as {"detail": "Token is expired", "code": "token_not_valid", "messages": [...]}.
    """
    detail = exc.detail
    if isinstance(detail, dict):
        detail = detail.get("detail", "Request failed")
    elif isinstance(detail, list):
        detail = detail[0] if detail else "Request failed"
    return str(detail)


def api_exception_handler(exc, context):
    """DRF exception handler that returns the standard error shape."""
    # DRF's own handler also sets headers such as Retry-After and WWW-Authenticate.
    response = exception_handler(exc, context)
    if response is None:
        # Not an API error. Django will log it and answer 500 through handler500.
        return None

    if isinstance(exc, exceptions.ValidationError):
        body = error_body("Validation failed", flatten_validation_errors(exc.detail))
    elif isinstance(exc, exceptions.Throttled):
        body = error_body("Too many requests. Try again later.")
    elif isinstance(exc, (Http404, exceptions.NotFound)):
        body = error_body("Not found")
    elif isinstance(exc, exceptions.APIException):
        body = error_body(api_exception_message(exc))
    else:
        body = error_body("Request failed")

    return Response(body, status=response.status_code, headers=dict(response.items()))


# --- Django-level errors, for URLs DRF never sees -----------------------------------------


def not_found(request, exception=None):
    return JsonResponse(
        error_body(f"Route {request.method} {request.path} not found"),
        status=status.HTTP_404_NOT_FOUND,
    )


def server_error(request):
    return JsonResponse(
        error_body("Internal server error"),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
