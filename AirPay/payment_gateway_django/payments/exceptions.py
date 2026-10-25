from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Idempotency-Key was already used for a different request."
    default_code = "conflict"


class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The payment rail is unavailable."
    default_code = "service_unavailable"
