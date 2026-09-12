from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WalletViewSet

router = DefaultRouter()
router.register("wallets", WalletViewSet, basename="wallets")

urlpatterns = [
    path("", include(router.urls)),
]
