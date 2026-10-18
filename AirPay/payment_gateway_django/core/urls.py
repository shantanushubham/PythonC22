from django.urls import path

from core.views import HealthView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
]
