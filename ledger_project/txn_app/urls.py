from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TxnViewSet

router = DefaultRouter()
router.register("txns", TxnViewSet, basename="txns")

urlpatterns = [
    path("", include(router.urls)),
]
