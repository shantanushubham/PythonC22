from django.db import DatabaseError, connection
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serialisers import HealthSerializer


class HealthView(APIView):
    """Liveness and readiness check. Load balancers and `docker` health checks call this."""

    # Public, and exempt from rate limiting so a probe is never turned away.
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes: list = []

    @extend_schema(
        operation_id="getHealth",
        tags=["Health"],
        summary="Check that the gateway and its database are up",
        responses={
            200: HealthSerializer,
            503: OpenApiResponse(
                HealthSerializer, description="The database cannot be reached."
            ),
        },
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            database = "ok"
        except DatabaseError:
            database = "unavailable"

        healthy = database == "ok"
        body = {
            "status": "ok" if healthy else "unavailable",
            "service": "airpay-gateway",
            "database": database,
        }
        return Response(
            body,
            status=(
                status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
        )
