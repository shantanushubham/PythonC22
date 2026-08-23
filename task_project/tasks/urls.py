from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LoginView, UserViewSet, TaskViewSet

router = DefaultRouter()

router.register("users", UserViewSet, basename="users")
router.register("tasks", TaskViewSet, basename="tasks")

urlpatterns = [
    # Auth
    path("login/", LoginView.as_view()),
    # Users
    path("", include(router.urls)),
]
