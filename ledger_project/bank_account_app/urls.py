from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BankAccountViewSet

router = DefaultRouter()
router.register("bank-accounts", BankAccountViewSet, basename="bank-accounts")

urlpatterns = [
    path("", include(router.urls)),
]
