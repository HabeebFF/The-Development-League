from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.league.urls")),
    path("api/v1/", include("apps.ingest.urls")),
    path("api/v1/", include("apps.maps.urls")),
    path("api/v1/", include("apps.rotations.urls")),
]
