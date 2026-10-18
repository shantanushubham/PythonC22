"""Top level routes.

Each feature app owns its URLs and is mounted here, so this file stays short.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("customers.urls")),
    path("api/v1/", include("payments.urls")),
    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

# JSON instead of Django's HTML error pages.
handler404 = "core.exceptions.not_found"
handler500 = "core.exceptions.server_error"
