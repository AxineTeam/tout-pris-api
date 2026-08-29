from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from tout_pris.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/", include("accounts.urls")),
    path("api/", include("households.urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("trips.urls")),
    path("api/auth/", include("allauth.headless.urls")),
    path("accounts/", include("allauth.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
