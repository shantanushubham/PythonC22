"""Payment endpoints. Every view here requires a valid API key.

A JWT access token is not accepted. That is the split: the dashboard uses JWT to
manage keys, and the payment API uses those keys.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serialisers import ErrorSerializer
from customers.authentication import APIKeyAuthentication


class PaymentAPIView(APIView):
    """Base for every payment endpoint."""

    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]


class PaymentWhoAmISerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    email = serializers.EmailField()
    company_name = serializers.CharField()
    api_key_id = serializers.UUIDField()
    api_key_prefix = serializers.CharField()
    api_key_expires_at = serializers.DateTimeField()


class PaymentWhoAmIView(PaymentAPIView):
    """Confirms that the API key works. Later payment endpoints sit next to this one."""

    @extend_schema(
        operation_id="paymentWhoAmI",
        tags=["Payments"],
        summary="Identify the customer behind an API key",
        responses={
            200: PaymentWhoAmISerializer,
            401: OpenApiResponse(ErrorSerializer, description="The API key is missing, invalid, revoked or expired."),
        },
    )
    def get(self, request):
        key = request.auth
        return Response(
            {
                "customer_id": request.user.id,
                "email": request.user.email,
                "company_name": request.user.company_name,
                "api_key_id": key.id,
                "api_key_prefix": key.prefix,
                "api_key_expires_at": key.expires_at,
            }
        )
