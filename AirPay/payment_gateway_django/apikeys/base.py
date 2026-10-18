from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apikeys.authentication import ApiKeyAuthentication
from apikeys.throttles import ApiKeyRateThrottle


class ApiKeyProtectedView(APIView):
    """Base class for every view of the payment system.

    Inherit from this and the view needs a valid, unexpired, unrevoked API key, and is
    rate limited per key. Inside the view, `request.user` is the customer and
    `request.auth` is the ApiKey.

    Only the API key is accepted here. A JWT access token is the way to manage an account
    (see /api-keys), and it does not open the payment system.
    """

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ApiKeyRateThrottle]
